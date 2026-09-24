"""Who may touch a per-user preference row.

User Theme Preference and User Sound Preference hold one row per user, keyed
by `user`. Both grant Theme Users create/read/write/delete `if_owner` — but
`owner` is whoever *inserted* the row, which is not the same thing as the
user the row is *for*. Nothing stopped a Theme User from posting a row with
someone else's `user` and a payload of their choosing straight to
/api/resource: the victim's Desk then rendered the attacker's CSS on every
boot, and because `owner` was the attacker, the victim could not save over
it — `if_owner` said the row was not theirs.

Two rules put this right, and both DocTypes apply them:

* `assert_own_row` — a row's `user` must be the session user, unless the
  caller is a System Manager (an admin resetting someone's preference is a
  legitimate thing to do) or server-side code has vouched for the write with
  `flags.ignore_permissions`, which is how install and patch code inserts.

* `own_row_permission` — the user a row is for may read, write and delete
  it whoever inserted it. This is what lets someone whose row was planted by
  another user save over it and take it back; `repair_owner` then sets
  `owner` to them so `if_owner` agrees from then on.
"""

import frappe
from frappe import _

OWN_ROW_RIGHTS = ("read", "write", "delete")


def is_privileged(user: str | None = None) -> bool:
	"""True for Administrator and anyone holding System Manager."""
	user = user or frappe.session.user
	return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def assert_own_row(doc) -> None:
	"""Refuse a row that is for someone other than the session user.

	Called from validate(), so it runs on every insert and save whether the
	write came from the app's own API, from /api/resource or from the form.
	"""
	if doc.flags.ignore_permissions:
		return
	user = frappe.session.user
	if doc.user == user or is_privileged(user):
		return
	frappe.throw(
		_("You can only change your own {0}.").format(_(doc.doctype)),
		frappe.PermissionError,
	)


def repair_owner(doc) -> None:
	"""Make `owner` the user the row is for.

	On insert Frappe sets `owner` to the session user, which is right for a
	user saving their own row and wrong for an admin creating one on their
	behalf — and it never changes afterwards on its own. Setting it here
	keeps `if_owner` (list views, reports, the form) in step with `user`.
	"""
	if doc.user and doc.owner != doc.user:
		doc.owner = doc.user


def own_row_permission(doc, permtype: str, user: str | None = None) -> bool:
	"""True if `user` is the row's user and their roles grant `permtype`.

	Answers the question `if_owner` gets wrong: the row belongs to `user`,
	not to whoever inserted it. Role permissions are still consulted, with
	the user treated as the owner — someone with no rights on the DocType at
	all (a Website User, say) gains nothing here.
	"""
	user = user or frappe.session.user
	if permtype not in OWN_ROW_RIGHTS or not doc.get("user") or doc.user != user:
		return False

	from frappe.permissions import get_role_permissions

	perms = get_role_permissions(doc.meta, user=user, is_owner=True)
	return bool(perms.get(permtype) or (perms.get("if_owner") or {}).get(permtype))
