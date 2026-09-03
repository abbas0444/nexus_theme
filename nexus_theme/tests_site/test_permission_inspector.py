"""Site-backed tests for the Permission Inspector.

Run with `bench --site <site> run-tests --app nexus_theme --module
nexus_theme.tests_site.test_permission_inspector`. They build a throwaway
submittable custom DocType, three roles (read / read+write / read+write+
create) and one user who holds all three, then check that the matrix reports
what Frappe enforces, that an edit made here changes what Frappe enforces
(asked through frappe.has_permission from the affected user's own session),
and that the guards refuse what the stock Permission Manager refuses.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from nexus_theme.permission_inspector import api

DT = "NXPI Test Doc"
ROLE_A = "NXPI Role A"  # read
ROLE_B = "NXPI Role B"  # read + write
ROLE_C = "NXPI Role C"  # read + write + create
ROLES = (ROLE_A, ROLE_B, ROLE_C)
USER = "nxpi-user@example.com"
PLAIN_USER = "nxpi-plain@example.com"  # a Desk user without System Manager
ADMIN = "Administrator"


RIGHTS = (
	"select",
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"print",
	"email",
	"report",
	"import",
	"export",
	"share",
)


def _perm(role, **flags):
	# A standard DocPerm row pre-ticks read/write/create/delete/print/email/
	# report/export/share, so zero everything and grant exactly what is named.
	base = {"role": role, "permlevel": 0, **dict.fromkeys(RIGHTS, 0), "read": 1}
	base.update(flags)
	return base


def _row(rows, name):
	for r in rows:
		if r["n"] == name:
			return r
	raise AssertionError(f"{name} not in matrix")


class TestPermissionInspector(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user(ADMIN)
		for role in ROLES:
			if not frappe.db.exists("Role", role):
				frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
					ignore_permissions=True
				)
		if frappe.db.exists("DocType", DT):
			frappe.delete_doc("DocType", DT, force=True, ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "DocType",
				"name": DT,
				"module": "Nexus Theme",
				"custom": 1,
				"is_submittable": 1,
				"allow_import": 1,
				"fields": [{"fieldname": "title", "fieldtype": "Data", "label": "Title"}],
				"permissions": [
					_perm(ROLE_A),
					_perm(ROLE_B, write=1),
					_perm(ROLE_C, write=1, create=1),
					_perm("System Manager", write=1, create=1, delete=1, submit=1, cancel=1, amend=1),
				],
			}
		).insert(ignore_permissions=True)
		for email, roles in ((USER, ROLES), (PLAIN_USER, ("Theme User",))):
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, force=True, ignore_permissions=True)
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "NXPI",
					"send_welcome_email": 0,
					"roles": [{"role": r} for r in roles],
				}
			).insert(ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user(ADMIN)
		frappe.db.delete("Custom DocPerm", {"parent": DT})
		frappe.db.delete("User Permission", {"user": USER})
		for email in (USER, PLAIN_USER):
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, force=True, ignore_permissions=True)
		if frappe.db.exists("DocType", DT):
			frappe.delete_doc("DocType", DT, force=True, ignore_permissions=True)
		for role in ROLES:
			if frappe.db.exists("Role", role):
				frappe.delete_doc("Role", role, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		frappe.set_user(ADMIN)
		# Every test starts from the standard rules shipped with the DocType.
		frappe.db.delete("Custom DocPerm", {"parent": DT})
		frappe.clear_cache(doctype=DT)
		frappe.local.role_permissions = {}

	def tearDown(self):
		frappe.set_user(ADMIN)

	# ------------------------------------------------------------------
	# helpers
	# ------------------------------------------------------------------

	def user_row(self):
		return _row(api.get_matrix("user", USER)["rows"], DT)

	def role_row(self, role):
		return _row(api.get_matrix("role", role)["rows"], DT)

	def engine_says(self, ptype, user=USER, doctype=DT):
		"""Ask Frappe from that user's own session, cache cleared, like a real request."""
		frappe.clear_cache(user=user)
		frappe.local.role_permissions = {}
		frappe.set_user(user)
		try:
			return bool(frappe.has_permission(doctype, ptype))
		finally:
			frappe.set_user(ADMIN)

	# ------------------------------------------------------------------
	# reading
	# ------------------------------------------------------------------

	def test_user_matrix_merges_all_roles_and_names_the_source(self):
		row = self.user_row()
		self.assertEqual(row["p"].get("read"), 1)
		self.assertEqual(row["p"].get("write"), 1)
		self.assertEqual(row["p"].get("create"), 1)
		self.assertIsNone(row["p"].get("delete"))
		self.assertIsNone(row["p"].get("submit"))
		self.assertEqual(row["s"]["read"], [ROLE_A, ROLE_B, ROLE_C])
		self.assertEqual(row["s"]["write"], [ROLE_B, ROLE_C])
		self.assertEqual(row["s"]["create"], [ROLE_C])
		# raw rules travel with the row (sorted) so the client can preview an edit
		self.assertEqual(row["r"][ROLE_A], ["read"])
		self.assertEqual(row["r"][ROLE_B], ["read", "write"])
		self.assertEqual(row["r"][ROLE_C], ["create", "read", "write"])
		# Select is implied by Read, and says so
		self.assertEqual(row["p"].get("select"), 1)
		self.assertTrue(row["s"]["select"][0].startswith("implied"))

	def test_matrix_agrees_with_the_engine(self):
		row = self.user_row()
		for ptype in (
			"read",
			"write",
			"create",
			"delete",
			"submit",
			"cancel",
			"print",
			"email",
			"report",
			"export",
			"share",
		):
			self.assertEqual(bool(row["p"].get(ptype)), self.engine_says(ptype), ptype)

	def test_role_matrix_shows_only_that_role(self):
		self.assertEqual(sorted(self.role_row(ROLE_A)["p"]), ["read", "select"])
		self.assertEqual(sorted(self.role_row(ROLE_B)["p"]), ["read", "select", "write"])
		self.assertEqual(sorted(self.role_row(ROLE_C)["p"]), ["create", "read", "select", "write"])
		self.assertNotIn("s", self.role_row(ROLE_B))  # source is the role itself

	def test_not_applicable_flags_follow_the_doctype(self):
		row = self.user_row()
		self.assertEqual(row["na"], [])  # submittable and importable
		single = _row(api.get_matrix("user", USER)["rows"], "System Settings")
		self.assertIn("submit", single["na"])
		self.assertIn("report", single["na"])
		self.assertIn("import", single["na"])

	def test_child_tables_are_hidden_unless_asked_and_never_editable(self):
		names = {r["n"] for r in api.get_matrix("user", USER)["rows"]}
		self.assertNotIn("Has Role", names)
		rows = api.get_matrix("user", USER, include_child=1)["rows"]
		child = _row(rows, "Has Role")
		self.assertTrue(child["lock"])
		self.assertRaises(
			frappe.ValidationError,
			api.save_changes,
			[{"doctype": "Has Role", "role": ROLE_A, "ptype": "read", "value": 1}],
		)

	def test_administrator_is_reported_as_bypassing(self):
		out = api.get_matrix("user", ADMIN)
		self.assertTrue(out["target"]["is_admin"])
		row = _row(out["rows"], DT)
		self.assertEqual(row["p"].get("delete"), 1)
		self.assertEqual(row["s"]["delete"], [ADMIN])

	def test_detail_asks_the_engine_and_lists_user_permissions(self):
		frappe.get_doc(
			{"doctype": "User Permission", "user": USER, "allow": "Role", "for_value": ROLE_A}
		).insert(ignore_permissions=True)
		try:
			d = api.get_doctype_detail("user", USER, DT)
			self.assertEqual(d["live"]["write"], 1)
			self.assertEqual(d["live"]["delete"], 0)
			self.assertEqual({r["role"] for r in d["rules"]}, set(ROLES))
			ups = api.get_user_permissions(USER)["rows"]
			self.assertEqual([(u["allow"], u["for_value"]) for u in ups], [("Role", ROLE_A)])
		finally:
			frappe.db.delete("User Permission", {"user": USER})

	# ------------------------------------------------------------------
	# writing: the change must be real
	# ------------------------------------------------------------------

	def test_turning_write_off_for_every_granting_role_is_enforced(self):
		self.assertTrue(self.engine_says("write"))
		out = api.save_changes(
			[
				{"doctype": DT, "role": ROLE_B, "ptype": "write", "value": 0},
				{"doctype": DT, "role": ROLE_C, "ptype": "write", "value": 0},
			],
			target_type="user",
			target=USER,
		)
		self.assertEqual({a["action"] for a in out["applied"]}, {"updated"})
		fresh = _row(out["rows"], DT)
		self.assertIsNone(fresh["p"].get("write"))
		self.assertEqual(fresh["p"].get("read"), 1)
		self.assertTrue(fresh["c"])  # now customised
		# Frappe itself, from the user's own session
		self.assertFalse(self.engine_says("write"))
		self.assertTrue(self.engine_says("read"))
		# and the Custom DocPerm rows are what changed
		self.assertEqual(
			frappe.db.get_value("Custom DocPerm", {"parent": DT, "role": ROLE_B, "permlevel": 0}, "write"), 0
		)

	def test_turning_write_off_for_one_role_keeps_it_via_the_other(self):
		api.save_changes([{"doctype": DT, "role": ROLE_B, "ptype": "write", "value": 0}])
		row = self.user_row()
		self.assertEqual(row["p"].get("write"), 1)
		self.assertEqual(row["s"]["write"], [ROLE_C])
		self.assertTrue(self.engine_says("write"))

	def test_every_flag_can_be_granted_and_revoked(self):
		grant = [
			{"doctype": DT, "role": ROLE_A, "ptype": p, "value": 1}
			for p in (
				"write",
				"create",
				"submit",
				"cancel",
				"amend",
				"delete",
				"print",
				"email",
				"report",
				"import",
				"export",
				"share",
			)
		]
		api.save_changes(grant)
		row = self.role_row(ROLE_A)
		for p in (
			"read",
			"write",
			"create",
			"submit",
			"cancel",
			"amend",
			"delete",
			"print",
			"email",
			"report",
			"import",
			"export",
			"share",
		):
			self.assertEqual(row["p"].get(p), 1, p)
		for p in ("submit", "cancel", "delete", "import", "share"):
			self.assertTrue(self.engine_says(p), p)

		revoke = [dict(c, value=0) for c in grant]
		api.save_changes(revoke)
		row = self.role_row(ROLE_A)
		self.assertEqual(sorted(row["p"]), ["read", "select"])
		# (write stays True for the user through Roles B and C; check the
		# flags only Role A had)
		for p in ("submit", "cancel", "delete", "import", "share"):
			self.assertFalse(self.engine_says(p), p)

	def test_write_off_drops_submit_cancel_amend_as_frappe_requires(self):
		# The ERPNext case: Accounts User on Sales Invoice has write+submit+
		# cancel+amend. Turning Write off must not fail on the leftovers.
		api.save_changes(
			[{"doctype": DT, "role": ROLE_B, "ptype": p, "value": 1} for p in ("submit", "cancel", "amend")]
		)
		self.assertTrue(self.engine_says("cancel"))
		out = api.save_changes([{"doctype": DT, "role": ROLE_B, "ptype": "write", "value": 0}])
		self.assertEqual(out["applied"][0]["changed"], {"write": 0, "submit": 0, "cancel": 0, "amend": 0})
		row = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": DT, "role": ROLE_B, "permlevel": 0},
			["read", "write", "submit", "cancel", "amend"],
			as_dict=True,
		)
		self.assertEqual(dict(row), {"read": 1, "write": 0, "submit": 0, "cancel": 0, "amend": 0})
		self.assertFalse(self.engine_says("cancel"))
		# and the other way round: Cancel on pulls in Submit and Write
		out = api.save_changes([{"doctype": DT, "role": ROLE_A, "ptype": "cancel", "value": 1}])
		self.assertEqual(out["applied"][0]["changed"], {"cancel": 1, "submit": 1, "write": 1})
		# a batch that contradicts itself is refused, not "fixed"
		self.assertRaises(
			frappe.ValidationError,
			api.save_changes,
			[
				{"doctype": DT, "role": ROLE_C, "ptype": "write", "value": 0},
				{"doctype": DT, "role": ROLE_C, "ptype": "submit", "value": 1},
			],
		)

	def test_a_role_without_a_rule_gets_one(self):
		# Error Log ships with a System Manager rule only, so the test user
		# starts with nothing on it.
		target = "Error Log"
		frappe.db.delete("Custom DocPerm", {"parent": target})
		self.assertFalse(self.engine_says("read", doctype=target))
		out = api.save_changes([{"doctype": target, "role": ROLE_A, "ptype": "read", "value": 1}])
		try:
			self.assertEqual(out["applied"][0]["action"], "added")
			row = frappe.db.get_value(
				"Custom DocPerm",
				{"parent": target, "role": ROLE_A, "permlevel": 0},
				["read", "export", "write"],
				as_dict=True,
			)
			self.assertEqual(
				(row.read, row.export, row.write), (1, 0, 0)
			)  # new_doc defaults must not leak in
			self.assertTrue(self.engine_says("read", doctype=target))
			self.assertFalse(self.engine_says("write", doctype=target))
		finally:
			frappe.db.delete("Custom DocPerm", {"parent": target})
			frappe.clear_cache(doctype=target)

	def test_clearing_every_basic_right_removes_the_rule(self):
		out = api.save_changes([{"doctype": DT, "role": ROLE_A, "ptype": "read", "value": 0}])
		self.assertEqual(out["applied"][0]["action"], "removed")
		self.assertFalse(frappe.db.exists("Custom DocPerm", {"parent": DT, "role": ROLE_A}))
		self.assertNotIn(ROLE_A, self.user_row()["s"]["read"])

	def test_the_last_rule_cannot_be_removed(self):
		frappe.db.delete("Custom DocPerm", {"parent": DT})
		applied = []
		for role in (ROLE_A, ROLE_B, ROLE_C):
			out = api.save_changes(
				[{"doctype": DT, "role": role, "ptype": p, "value": 0} for p in ("read", "write", "create")]
			)
			applied.append((out["applied"], frappe.get_all("Custom DocPerm", {"parent": DT}, pluck="role")))
		# only System Manager's rule is left
		self.assertEqual(
			frappe.get_all("Custom DocPerm", {"parent": DT}, pluck="role"), ["System Manager"], applied
		)
		self.assertRaises(
			frappe.ValidationError,
			api.save_changes,
			[
				{"doctype": DT, "role": "System Manager", "ptype": p, "value": 0}
				for p in ("read", "write", "create", "submit", "cancel", "amend")
			],
		)
		self.assertEqual(frappe.db.count("Custom DocPerm", {"parent": DT}), 1)

	def test_a_failed_batch_leaves_nothing_behind(self):
		before = frappe.db.count("Custom DocPerm", {"parent": DT})
		self.assertRaises(
			frappe.ValidationError,
			api.save_changes,
			[
				{"doctype": DT, "role": ROLE_A, "ptype": "write", "value": 1},  # fine on its own
				{"doctype": "ToDo", "role": ROLE_B, "ptype": "submit", "value": 1},  # not submittable
			],
		)
		self.assertEqual(frappe.db.count("Custom DocPerm", {"parent": DT}), before)
		self.assertFalse(frappe.db.exists("Custom DocPerm", {"parent": "ToDo"}))
		self.assertIsNone(self.role_row(ROLE_A)["p"].get("write"))

	# ------------------------------------------------------------------
	# validation mirrors Frappe's own
	# ------------------------------------------------------------------

	def test_dependency_rules(self):
		bad = [
			[{"doctype": "ToDo", "role": ROLE_B, "ptype": "submit", "value": 1}],  # not submittable
			[{"doctype": "ToDo", "role": ROLE_B, "ptype": "amend", "value": 1}],  # not submittable
			[{"doctype": "Error Log", "role": ROLE_A, "ptype": "import", "value": 1}],  # not importable
			[  # contradictory: import needs create
				{"doctype": DT, "role": ROLE_A, "ptype": "import", "value": 1},
				{"doctype": DT, "role": ROLE_A, "ptype": "create", "value": 0},
			],
			[{"doctype": DT, "role": ROLE_A, "ptype": "bogus", "value": 1}],  # unknown flag
			[{"doctype": DT, "role": "No Such Role", "ptype": "read", "value": 1}],
			[{"doctype": "No Such DocType", "role": ROLE_A, "ptype": "read", "value": 1}],
			[{"doctype": DT, "role": ROLE_A, "ptype": "read", "value": 5}],
			"not a list",
		]
		for changes in bad:
			with self.subTest(changes=changes):
				self.assertRaises(frappe.ValidationError, api.save_changes, changes)
		self.assertFalse(frappe.db.exists("Custom DocPerm", {"parent": "ToDo"}))
		self.assertFalse(frappe.db.exists("Custom DocPerm", {"parent": "Error Log"}))
		# a single flag pulls in what it needs, as the UI does
		api.save_changes([{"doctype": DT, "role": ROLE_A, "ptype": "import", "value": 1}])
		self.assertEqual(sorted(self.role_row(ROLE_A)["p"]), ["create", "import", "read", "select"])
		self.assertTrue(self.engine_says("import"))

	def test_single_doctypes_drop_report_import_export_silently(self):
		api.save_changes(
			[
				{"doctype": "System Settings", "role": ROLE_A, "ptype": "read", "value": 1},
				{"doctype": "System Settings", "role": ROLE_A, "ptype": "report", "value": 1},
			]
		)
		try:
			row = frappe.db.get_value(
				"Custom DocPerm",
				{"parent": "System Settings", "role": ROLE_A, "permlevel": 0},
				["read", "report"],
				as_dict=True,
			)
			self.assertEqual((row.read, row.report), (1, 0))
		finally:
			frappe.db.delete("Custom DocPerm", {"parent": "System Settings"})
			frappe.clear_cache(doctype="System Settings")

	# ------------------------------------------------------------------
	# security
	# ------------------------------------------------------------------

	def test_only_system_managers_may_read_or_write(self):
		frappe.set_user(PLAIN_USER)
		self.assertRaises(frappe.PermissionError, api.get_options)
		self.assertRaises(frappe.PermissionError, api.get_matrix, "user", USER)
		self.assertRaises(frappe.PermissionError, api.get_doctype_detail, "user", USER, DT)
		self.assertRaises(frappe.PermissionError, api.get_user_permissions, USER)
		self.assertRaises(frappe.PermissionError, api.refresh_cache)
		self.assertRaises(
			frappe.PermissionError,
			api.save_changes,
			[{"doctype": DT, "role": ROLE_A, "ptype": "write", "value": 1}],
		)
		frappe.set_user(ADMIN)
		self.assertIsNone(self.role_row(ROLE_A)["p"].get("write"))

	def test_administrator_role_rules_are_locked(self):
		self.assertRaises(
			frappe.ValidationError,
			api.save_changes,
			[{"doctype": DT, "role": ADMIN, "ptype": "read", "value": 1}],
		)

	def test_a_manager_who_is_not_administrator_cannot_touch_automatic_roles(self):
		email = "nxpi-manager@example.com"
		if frappe.db.exists("User", email):
			frappe.delete_doc("User", email, force=True, ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "NXPI Manager",
				"send_welcome_email": 0,
				"roles": [{"role": "System Manager"}],
			}
		).insert(ignore_permissions=True)
		try:
			frappe.set_user(email)
			self.assertIn("All", api.get_options()["locked_roles"])
			self.assertRaises(
				frappe.ValidationError,
				api.save_changes,
				[{"doctype": DT, "role": "All", "ptype": "read", "value": 1}],
			)
			# but ordinary roles are fine for them
			api.save_changes([{"doctype": DT, "role": ROLE_A, "ptype": "write", "value": 1}])
			frappe.set_user(ADMIN)
			self.assertEqual(self.role_row(ROLE_A)["p"].get("write"), 1)
		finally:
			frappe.set_user(ADMIN)
			frappe.delete_doc("User", email, force=True, ignore_permissions=True)
