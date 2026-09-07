"""Permission Inspector — a read/write window onto Frappe's own permission system.

Nothing here is a permission engine. Every number the inspector shows is read
from the records Frappe itself evaluates (DocPerm, Custom DocPerm, Has Role,
User Permission) through Frappe's own helpers, and every change it makes goes
through the same Custom DocPerm mechanism the stock Role Permission Manager
writes to. If this module were deleted, no permission on the site would change.

How Frappe v16 decides a role permission (frappe.permissions.get_role_permissions):

* Rules are the DocPerm rows of the DocType, replaced wholesale by that
  DocType's Custom DocPerm rows once any exist (frappe.model.meta).
* Only level-0 rules grant document access; higher levels gate fields.
* A user's effective flag is the OR across the rules of every role they hold.
* A rule marked "if owner" grants the flag only for documents the user owns,
  unless another rule grants it outright.
* Submit needs a submittable DocType; Import needs an importable one; Select
  is implied by Read.

The matrix below reproduces exactly that evaluation so it can also explain
*which* role is responsible, and the detail view asks frappe.has_permission
directly so the answer can be checked against the engine itself.
"""

import json
from collections import defaultdict

import frappe
import frappe.permissions
from frappe import _
from frappe.core.doctype.doctype.doctype import clear_permissions_cache
from frappe.model import table_fields
from frappe.permissions import (
	AUTOMATIC_ROLES,
	get_all_perms,
	get_linked_doctypes,
	get_valid_perms,
	setup_custom_perms,
)
from frappe.permissions import (
	rights as std_rights,
)
from frappe.utils import cint, cstr
from frappe.utils.user import get_users_with_role


def get_doctype_ptype_map() -> dict:
	"""Custom permission types, keyed by DocType.

	Frappe 16 added a "Permission Type" DocType so a site can invent its own
	rights beside read/write/create. Frappe 15 has no such thing, so there is
	nothing to add and every DocType uses the standard rights alone. Kept as a
	function of the same name so the rest of this file reads identically on
	both branches.
	"""
	return {}


def update_custom_docperm(docperm: str, values: dict) -> None:
	"""Save changed flags onto one Custom DocPerm row.

	Frappe 16 ships this as a helper; on 15 it is these three lines, which is
	all the helper ever was.
	"""
	doc = frappe.get_doc("Custom DocPerm", docperm)
	doc.update(values)
	doc.save(ignore_permissions=True)


try:  # the stock manager's own exclusion list; fall back to its known value
	from frappe.core.page.permission_manager.permission_manager import (
		not_allowed_in_permission_manager,
	)
except ImportError:  # pragma: no cover - only if Frappe moves the module
	not_allowed_in_permission_manager = ["DocType", "Patch Log", "Module Def"]

MANAGER_ROLE = "System Manager"
ADMIN = "Administrator"

# frappe.model.meta.set_custom_permissions never applies Custom DocPerm to
# these, so a rule written for them would silently do nothing.
CORE_LOCKED = ("DocType", "DocField", "DocPerm", "Custom DocPerm")

# Rights that make a rule "exist" for Frappe's validator (check_atleast_one_set).
BASIC_RIGHTS = ("select", "read", "write", "submit", "cancel", "create")

# Frappe v16 added a "mask" flag beside the standard rights (it is not in
# std_rights because it gates masked field values, not documents). Shown as a
# column when the installed Frappe has the field.
MASK = "mask"

# Display order and tooltips. Keys are Frappe's own ptype names.
COLUMNS = [
	("read", "Read", "Open and view documents of this type."),
	("write", "Write", "Edit and save existing documents."),
	("create", "Create", "Make new documents."),
	("submit", "Submit", "Submit documents. Only for submittable DocTypes; needs Write."),
	("cancel", "Cancel", "Cancel submitted documents. Needs Submit."),
	("amend", "Amend", "Amend a cancelled document. Needs Write on a submittable DocType."),
	("delete", "Delete", "Delete documents."),
	("print", "Print", "Print documents and use print formats."),
	("email", "Email", "Send documents by email."),
	("report", "Report", "Use Report Builder and reports on this type. Not for Single DocTypes."),
	("import", "Import", "Use Data Import. Needs Create and an importable DocType."),
	("export", "Export", "Export from lists and reports. Not for Single DocTypes."),
	("share", "Share", "Share individual documents with other users."),
	("select", "Select", "Pick documents in Link fields without full Read. Implied by Read."),
	(MASK, "Mask", "See the real value of fields that are masked for everyone else (Frappe v16)."),
]


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def _assert_manager() -> None:
	"""Same gate as Frappe's Role Permission Manager: System Manager only.

	Raises PermissionError, so a call from a user without the role fails
	before any data is read — hiding the page is not what protects it."""
	frappe.only_for(MANAGER_ROLE)


def _locked_roles() -> set[str]:
	"""Roles whose rules may not be edited here — mirrors get_roles_and_doctypes
	in the stock manager. Administrator's rules are never editable; a manager
	who is not Administrator also cannot touch the automatic roles (All, Guest,
	Desk User) or roles that define a custom User Type."""
	locked = {ADMIN}
	if frappe.session.user != ADMIN:
		locked.update(AUTOMATIC_ROLES)
		locked.update(frappe.get_all("User Type", filters={"is_standard": 0}, pluck="role"))
	return locked


def _lock_reason(meta) -> str | None:
	if meta.istable:
		return _("Child table: it takes the permissions of its parent DocType.")
	if meta.name in not_allowed_in_permission_manager or meta.name in CORE_LOCKED:
		return _("Frappe manages this DocType's permissions itself.")
	return None


def _assert_role_allowed_for_doctype(meta, role: str) -> None:
	"""Mirror of validate_permission_for_all_role in frappe's DocType controller."""
	if frappe.session.user == ADMIN or not meta.custom:
		return
	if role in AUTOMATIC_ROLES or cint(frappe.db.get_value("Role", role, "is_custom")):
		frappe.throw(
			_("Only Administrator can give the role {0} access to the custom DocType {1}.").format(
				frappe.bold(role), frappe.bold(meta.name)
			),
			title=_("Not Allowed"),
		)


# ---------------------------------------------------------------------------
# Rights
# ---------------------------------------------------------------------------


def _has_mask() -> bool:
	return frappe.get_meta("Custom DocPerm").has_field(MASK)


def _base_rights() -> list[str]:
	rights = list(std_rights)
	if _has_mask():
		rights.append(MASK)
	return rights


def _rights_for(doctype: str, base: list[str] | None = None) -> list[str]:
	"""std rights (+ mask) plus this DocType's custom Permission Types."""
	rights = list(base or _base_rights())
	for extra in get_doctype_ptype_map().get(doctype, []):
		if extra not in rights:
			rights.append(extra)
	return rights


def _not_applicable(meta) -> list[str]:
	"""Flags Frappe forces off for this DocType regardless of any rule."""
	na = []
	if not cint(meta.is_submittable):
		na += ["submit", "cancel", "amend"]
	if not cint(meta.allow_import):
		na.append("import")
	if cint(meta.issingle):
		na += ["report", "export"]
		if "import" not in na:
			na.append("import")
	return na


def _columns() -> list[dict]:
	has_mask = _has_mask()
	return [
		{"key": key, "label": _(label), "description": _(desc)}
		for key, label, desc in COLUMNS
		if key != MASK or has_mask
	]


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_options():
	_assert_manager()
	return {
		"columns": _columns(),
		"rights": _base_rights(),
		"locked_roles": sorted(_locked_roles()),
		"session_is_admin": frappe.session.user == ADMIN,
		"custom_ptypes": get_doctype_ptype_map(),
	}


# ---------------------------------------------------------------------------
# Target info
# ---------------------------------------------------------------------------


def _user_info(user: str) -> dict:
	doc = frappe.db.get_value(
		"User",
		user,
		["name", "full_name", "enabled", "user_type", "last_login", "user_image"],
		as_dict=True,
	)
	if not doc:
		frappe.throw(_("User {0} does not exist").format(frappe.bold(user)), frappe.DoesNotExistError)

	assigned = frappe.get_all(
		"Has Role", filters={"parenttype": "User", "parent": user}, pluck="role", order_by="idx"
	)
	# What the engine actually uses, automatic roles included.
	effective = frappe.get_roles(user)
	disabled_roles = (
		set(frappe.get_all("Role", filters={"name": ["in", assigned], "disabled": 1}, pluck="name"))
		if assigned
		else set()
	)

	return {
		"type": "user",
		"name": doc.name,
		"label": doc.full_name or doc.name,
		"enabled": cint(doc.enabled),
		"user_type": doc.user_type,
		"last_login": cstr(doc.last_login),
		"user_image": doc.user_image,
		"is_admin": user == ADMIN,
		"is_system_manager": MANAGER_ROLE in effective,
		"roles": sorted(set(assigned)),
		"automatic_roles": sorted(r for r in effective if r in AUTOMATIC_ROLES),
		"disabled_roles": sorted(disabled_roles),
		"blocked_modules": frappe.get_all(
			"Block Module", filters={"parenttype": "User", "parent": user}, pluck="module"
		),
		"user_permission_count": frappe.db.count("User Permission", {"user": user}),
	}


def _role_info(role: str) -> dict:
	doc = frappe.db.get_value(
		"Role",
		role,
		["name", "disabled", "desk_access", "is_custom", "two_factor_auth", "restrict_to_domain"],
		as_dict=True,
	)
	if not doc:
		frappe.throw(_("Role {0} does not exist").format(frappe.bold(role)), frappe.DoesNotExistError)
	users = get_users_with_role(role)
	return {
		"type": "role",
		"name": doc.name,
		"label": doc.name,
		"disabled": cint(doc.disabled),
		"desk_access": cint(doc.desk_access),
		"is_custom": cint(doc.is_custom),
		"two_factor_auth": cint(doc.two_factor_auth),
		"restrict_to_domain": doc.restrict_to_domain,
		"is_automatic": role in AUTOMATIC_ROLES,
		"user_count": len(users),
		"users": sorted(users)[:50],
	}


def _target_info(target_type: str, target: str) -> dict:
	if target_type == "user":
		return _user_info(target)
	if target_type == "role":
		return _role_info(target)
	frappe.throw(_("Pick either a User or a Role."))


# ---------------------------------------------------------------------------
# Matrix
# ---------------------------------------------------------------------------

DOCTYPE_FIELDS = [
	"name",
	"module",
	"istable",
	"issingle",
	"is_submittable",
	"allow_import",
	"is_tree",
	"is_virtual",
	"custom",
	"in_create",
	"read_only",
	"restrict_to_domain",
]


def _doctypes(include_child: bool, only: list[str] | None = None) -> list:
	filters = {}
	if only:
		filters["name"] = ["in", only]
	elif not include_child:
		filters["istable"] = 0
	rows = frappe.get_all("DocType", fields=DOCTYPE_FIELDS, filters=filters, order_by="name asc")

	active = set(frappe.get_active_domains() or [])
	return [r for r in rows if not r.restrict_to_domain or r.restrict_to_domain in active]


def _flags(d) -> dict:
	return {
		"single": cint(d.issingle),
		"submittable": cint(d.is_submittable),
		"importable": cint(d.allow_import),
		"tree": cint(d.is_tree),
		"virtual": cint(d.is_virtual),
		"custom": cint(d.custom),
		"child": cint(d.istable),
		"in_create": cint(d.in_create),
		"read_only": cint(d.read_only),
	}


def _granted(rule, rights: list[str]) -> list[str]:
	return [r for r in rights if cint(rule.get(r))]


def _evaluate(rules: list, rights: list[str], na: list[str]) -> tuple[dict, dict]:
	"""Reproduce get_role_permissions for one DocType over `rules` (level 0 only).

	Returns (perms, sources): perms maps ptype -> 1 (granted), 2 (only for
	documents the user owns) or nothing (not granted); sources maps ptype ->
	the roles responsible, "(if owner)" suffixed where that is the reason.
	"""
	perms: dict[str, int] = {}
	sources: dict[str, list[str]] = {}
	has_owner_rule = any(cint(r.get("if_owner")) for r in rules)

	for ptype in rights:
		if ptype in na:
			continue
		granting = [r for r in rules if cint(r.get(ptype))]
		if not granting:
			continue
		outright = [r for r in granting if not cint(r.get("if_owner"))]
		if has_owner_rule and not outright and ptype != "create":
			perms[ptype] = 2
		else:
			perms[ptype] = 1
		names = sorted({r.role for r in outright}) + sorted(
			{f"{r.role} ({_('if owner')})" for r in granting if cint(r.get("if_owner"))}
		)
		sources[ptype] = names

	# has_permission falls back to Read when Select is not granted.
	if "select" not in perms and "select" in rights and perms.get("read"):
		perms["select"] = perms["read"]
		sources["select"] = [_("implied by Read"), *sources.get("read", [])]

	return perms, sources


def _build_rows(target_type: str, target: str, include_child: bool, only: list[str] | None = None):
	base_rights = _base_rights()
	ptype_map = get_doctype_ptype_map()
	doctypes = _doctypes(include_child, only)
	customised = set(frappe.get_all("Custom DocPerm", pluck="parent", distinct=True))
	locked_roles = _locked_roles()

	admin_target = target_type == "user" and target == ADMIN
	if admin_target:
		rules_by_dt: dict[str, list] = {}
	elif target_type == "user":
		rules_by_dt = defaultdict(list)
		for p in get_valid_perms(user=target):
			rules_by_dt[p.parent].append(p)
	else:
		rules_by_dt = defaultdict(list)
		for p in get_all_perms(target):
			if cint(p.permlevel) == 0:
				rules_by_dt[p.parent].append(p)

	out = []
	for d in doctypes:
		rights = _rights_for(d.name, base_rights) if d.name in ptype_map else base_rights
		na = _not_applicable(d)
		row = {
			"n": d.name,
			"m": d.module,
			"f": _flags(d),
			"c": 1 if d.name in customised else 0,
			"na": na,
			"lock": _lock_reason(d),
		}
		if d.name in ptype_map:
			row["x"] = ptype_map[d.name]

		if admin_target:
			row["p"] = {r: 1 for r in rights if r not in na}
			row["s"] = {r: [ADMIN] for r in row["p"]}
			out.append(row)
			continue

		rules = rules_by_dt.get(d.name, [])
		perms, sources = _evaluate(rules, rights, na)
		row["p"] = perms
		if target_type == "user":
			row["s"] = sources

		# The raw rules, so the client can preview an edit with the same
		# maths before anything is saved.
		plain: dict[str, set] = defaultdict(set)
		owner: dict[str, set] = defaultdict(set)
		for r in rules:
			bucket = owner if cint(r.get("if_owner")) else plain
			bucket[r.role].update(_granted(r, rights))
		if plain:
			row["r"] = {role: sorted(v) for role, v in plain.items()}
		if owner:
			row["o"] = {role: sorted(v) for role, v in owner.items()}
		if any(role in locked_roles for role in list(plain) + list(owner)):
			row["lr"] = sorted({role for role in list(plain) + list(owner) if role in locked_roles})
		out.append(row)
	return out


@frappe.whitelist()
def get_matrix(target_type: str, target: str, include_child: int = 0):
	"""Everything the matrix needs in one round-trip."""
	_assert_manager()
	target_type = cstr(target_type).lower()
	target = cstr(target).strip()
	if not target:
		frappe.throw(_("Pick a User or a Role first."))
	info = _target_info(target_type, target)
	return {
		"target": info,
		"columns": _columns(),
		"rights": _base_rights(),
		"locked_roles": sorted(_locked_roles()),
		"rows": _build_rows(target_type, target, cint(include_child)),
	}


# ---------------------------------------------------------------------------
# Detail for one DocType
# ---------------------------------------------------------------------------


def _live_check(doctype: str, user: str, rights: list[str]) -> dict | None:
	"""Ask the engine itself. This is the proof that a saved change is real."""
	meta = frappe.get_meta(doctype)
	if meta.istable:
		return None  # needs a parent; the engine checks the parent instead
	out = {}
	saved_log = frappe.local.message_log
	frappe.local.message_log = []
	try:
		for ptype in rights:
			try:
				out[ptype] = (
					1 if frappe.permissions.has_permission(doctype, ptype, user=user, print_logs=False) else 0
				)
			except Exception:
				out[ptype] = 0
	finally:
		frappe.local.message_log = saved_log
	return out


def _rule_rows(doctype: str, roles: list[str] | None, rights: list[str], perm_doctype=None) -> list[dict]:
	"""All rules (every level, if-owner included) for the roles in scope.

	Without `perm_doctype` this is what the engine sees (meta.permissions:
	Custom DocPerm when present, else DocPerm). With perm_doctype="DocPerm"
	it is the standard set shipped in code, for a before/after comparison.
	"""
	if perm_doctype:
		perms = frappe.get_all(
			perm_doctype, fields="*", filters={"parent": doctype}, order_by="permlevel, idx"
		)
	else:
		perms = frappe.get_meta(doctype).permissions
	out = []
	for p in perms:
		if roles is not None and p.role not in roles:
			continue
		out.append(
			{
				"role": p.role,
				"permlevel": cint(p.permlevel),
				"if_owner": cint(p.get("if_owner")),
				"granted": _granted(p, rights),
			}
		)
	out.sort(key=lambda r: (r["permlevel"], r["if_owner"], r["role"]))
	return out


@frappe.whitelist()
def get_doctype_detail(target_type: str, target: str, doctype: str):
	_assert_manager()
	target_type = cstr(target_type).lower()
	meta = frappe.get_meta(doctype)
	rights = _rights_for(doctype)

	if target_type == "user":
		roles = None if target == ADMIN else frappe.get_roles(target)
		live = {r: 1 for r in rights} if target == ADMIN else _live_check(doctype, target, rights)
		linked = set(get_linked_doctypes(doctype)) if not meta.istable else {doctype}
		ups = frappe.get_all(
			"User Permission",
			filters={"user": target, "allow": ["in", sorted(linked)]},
			fields=[
				"name",
				"allow",
				"for_value",
				"applicable_for",
				"apply_to_all_doctypes",
				"is_default",
				"hide_descendants",
			],
			order_by="allow, for_value",
		)
	else:
		roles = [target]
		live = None
		ups = []

	customised = bool(frappe.db.exists("Custom DocPerm", {"parent": doctype}))
	parents = []
	if meta.istable:
		parents = frappe.get_all(
			"DocField",
			filters={"fieldtype": ["in", table_fields], "options": doctype},
			pluck="parent",
			distinct=True,
		)
	try:
		app = frappe.get_module_app(meta.module)
	except Exception:
		app = None

	return {
		"doctype": doctype,
		"module": meta.module,
		"app": app,
		"description": meta.description,
		"flags": _flags(meta),
		"na": _not_applicable(meta),
		"rights": rights,
		"custom_ptypes": get_doctype_ptype_map().get(doctype, []),
		"customised": customised,
		"lock": _lock_reason(meta),
		"rules": _rule_rows(doctype, roles, rights),
		"standard_rules": _rule_rows(doctype, roles, rights, perm_doctype="DocPerm") if customised else None,
		"live": live,
		"user_permissions": ups,
		"parents": parents,
	}


# ---------------------------------------------------------------------------
# User Permissions (the other layer — shown, never merged into the matrix)
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_user_permissions(user: str):
	_assert_manager()
	if not frappe.db.exists("User", user):
		frappe.throw(_("User {0} does not exist").format(frappe.bold(user)), frappe.DoesNotExistError)
	rows = frappe.get_all(
		"User Permission",
		filters={"user": user},
		fields=[
			"name",
			"allow",
			"for_value",
			"applicable_for",
			"apply_to_all_doctypes",
			"is_default",
			"hide_descendants",
			"creation",
		],
		order_by="allow asc, for_value asc",
	)
	return {
		"user": user,
		"strict": cint(frappe.get_system_settings("apply_strict_user_permissions")),
		"rows": rows,
	}


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def _parse_changes(changes) -> list[dict]:
	if isinstance(changes, str):
		try:
			changes = json.loads(changes)
		except ValueError:
			frappe.throw(_("Changes must be a JSON list."))
	if not isinstance(changes, list):
		frappe.throw(_("Changes must be a JSON list."))
	out = []
	for i, ch in enumerate(changes, start=1):
		if not isinstance(ch, dict):
			frappe.throw(_("Change {0} is not an object.").format(i))
		doctype = cstr(ch.get("doctype")).strip()
		role = cstr(ch.get("role")).strip()
		ptype = cstr(ch.get("ptype")).strip().lower()
		value = ch.get("value")
		if not (doctype and role and ptype):
			frappe.throw(_("Change {0} needs a doctype, a role and a permission type.").format(i))
		if value not in (0, 1, "0", "1", True, False):
			frappe.throw(_("Change {0}: value must be 0 or 1.").format(i))
		out.append({"doctype": doctype, "role": role, "ptype": ptype, "value": 1 if cint(value) else 0})
	return out


# Frappe's dependency rules (frappe.core.doctype.doctype.validate_permissions):
# a flag pulls in what it needs when ticked, and drops what needed it when
# cleared. Mirrored on the client so the preview and the save agree.
NEEDS = {"cancel": ("submit", "write"), "submit": ("write",), "amend": ("write",), "import": ("create",)}
DEPENDENTS = {"write": ("submit", "cancel", "amend"), "submit": ("cancel",), "create": ("import",)}


def _cascade(desired: dict, values: dict) -> None:
	"""Apply `values` to `desired`, cascading through NEEDS/DEPENDENTS.

	"Write off" therefore also clears Submit, Cancel and Amend — which is what
	Frappe requires of a valid rule — instead of failing on a row that still
	carries them. A flag the caller set explicitly is never overridden by a
	cascade; a contradictory batch is left for _validate_rule to refuse."""

	def turn(ptype, value):
		if desired.get(ptype) == value:
			return
		desired[ptype] = value
		for other in NEEDS.get(ptype, ()) if value else DEPENDENTS.get(ptype, ()):
			if other in values and values[other] != value:
				continue
			turn(other, value)

	for ptype, value in values.items():
		turn(ptype, value)


def _validate_rule(meta, role: str, d: dict) -> None:
	"""The dependency rules from frappe's validate_permissions, applied to the
	rule this save produces, with messages that name the role and DocType."""

	def fail(msg):
		frappe.throw(
			_("{0} on {1}: {2}").format(frappe.bold(role), frappe.bold(meta.name), msg),
			title=_("Invalid Permission Rule"),
		)

	if d.get("cancel") and not d.get("submit"):
		fail(_("Cancel needs Submit."))
	if (d.get("submit") or d.get("cancel") or d.get("amend")) and not d.get("write"):
		fail(_("Submit, Cancel and Amend need Write."))
	if d.get("import") and not d.get("create"):
		fail(_("Import needs Create."))
	if (d.get("submit") or d.get("amend") or d.get("cancel")) and not cint(meta.is_submittable):
		fail(_("this DocType is not submittable, so Submit, Cancel and Amend cannot be set."))
	if d.get("import") and not cint(meta.allow_import):
		fail(_("this DocType does not allow Data Import, so Import cannot be set."))
	if cint(meta.issingle):
		# Frappe zeroes these on Single DocTypes rather than refusing them.
		for key in ("report", "import", "export"):
			d[key] = 0


def _apply_rule_changes(doctype: str, role: str, values: dict) -> dict:
	meta = frappe.get_meta(doctype)
	if lock := _lock_reason(meta):
		frappe.throw(_("{0}: {1}").format(frappe.bold(doctype), lock), title=_("Not Editable"))
	_assert_role_allowed_for_doctype(meta, role)

	rights = _rights_for(doctype)
	for ptype in values:
		if ptype not in rights:
			frappe.throw(
				_("{0} is not a permission type of {1}.").format(frappe.bold(ptype), frappe.bold(doctype))
			)

	# From here on the DocType is governed by Custom DocPerm rows — the same
	# copy-on-first-edit the stock manager performs.
	setup_custom_perms(doctype)

	name = frappe.db.get_value(
		"Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0}
	)
	current = frappe.get_doc("Custom DocPerm", name) if name else None

	desired = {r: (cint(current.get(r)) if current else 0) for r in rights}
	_cascade(desired, values)
	_validate_rule(meta, role, desired)

	if not any(desired.get(r) for r in BASIC_RIGHTS):
		# Frappe's validator refuses a rule with no basic right, so an
		# all-clear means "remove the rule", as the stock manager's Remove does.
		if not current:
			return {"doctype": doctype, "role": role, "action": "unchanged"}
		if frappe.db.count("Custom DocPerm", {"parent": doctype}) <= 1:
			frappe.throw(
				_(
					"{0} must keep at least one permission rule. Clear a different role's rule first, or leave this one a basic right."
				).format(frappe.bold(doctype)),
				title=_("Cannot Remove Last Rule"),
			)
		frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)
		return {"doctype": doctype, "role": role, "action": "removed"}

	if current:
		changed = {r: v for r, v in desired.items() if cint(current.get(r)) != v}
		if not changed:
			return {"doctype": doctype, "role": role, "action": "unchanged"}
		update_custom_docperm(name, changed)
		return {"doctype": doctype, "role": role, "action": "updated", "changed": changed}

	doc = frappe.new_doc("Custom DocPerm")
	doc.update(
		{
			"parent": doctype,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": role,
			"permlevel": 0,
			"if_owner": 0,
		}
	)
	doc.update(dict.fromkeys(rights, 0))  # new_doc pre-ticks read/export; start clean
	doc.update(desired)
	doc.insert(ignore_permissions=True)
	return {"doctype": doctype, "role": role, "action": "added", "changed": desired}


@frappe.whitelist()
def save_changes(changes, target_type: str | None = None, target: str | None = None, include_child: int = 0):
	"""Apply a batch of {doctype, role, ptype, value} edits as one transaction.

	Every edit is validated first; any failure rolls the whole batch back and
	reports which rule was wrong. On success the permission caches are
	cleared and the affected matrix rows are re-read from the database and
	returned, so the client shows what Frappe now enforces, not what it hoped.
	"""
	_assert_manager()
	changes = _parse_changes(changes)
	if not changes:
		frappe.throw(_("Nothing to save."))

	locked = _locked_roles()
	grouped: dict[tuple[str, str], dict] = {}
	for ch in changes:
		if not frappe.db.exists("DocType", ch["doctype"]):
			frappe.throw(_("DocType {0} does not exist.").format(frappe.bold(ch["doctype"])))
		if not frappe.db.exists("Role", ch["role"]):
			frappe.throw(_("Role {0} does not exist.").format(frappe.bold(ch["role"])))
		if ch["role"] in locked:
			frappe.throw(
				_("The rules of role {0} cannot be edited here.").format(frappe.bold(ch["role"])),
				title=_("Locked Role"),
			)
		grouped.setdefault((ch["doctype"], ch["role"]), {})[ch["ptype"]] = ch["value"]

	# A savepoint rather than a bare rollback: it undoes exactly this batch and
	# nothing an enclosing transaction (a script, a test, a patch) did before.
	# In a request the two are equivalent, since Frappe rolls back on error.
	savepoint = "nexus_permission_inspector"
	frappe.db.savepoint(savepoint)
	applied = []
	try:
		for (doctype, role), values in grouped.items():
			applied.append(_apply_rule_changes(doctype, role, values))
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		raise
	frappe.db.release_savepoint(savepoint)

	doctypes = sorted({dt for dt, _r in grouped})
	for doctype in doctypes:
		clear_permissions_cache(doctype)
	frappe.local.role_permissions = {}

	out = {"applied": applied, "doctypes": doctypes}
	if target_type and target:
		out["rows"] = _build_rows(cstr(target_type).lower(), cstr(target), cint(include_child), only=doctypes)
	return out


@frappe.whitelist()
def refresh_cache(target_type: str | None = None, target: str | None = None):
	"""Drop cached roles/permissions so the next read reflects the database."""
	_assert_manager()
	from frappe.cache_manager import clear_user_cache

	if cstr(target_type).lower() == "user" and target:
		clear_user_cache(cstr(target))
	else:
		clear_user_cache()
	frappe.local.role_permissions = {}
	return {"ok": 1}
