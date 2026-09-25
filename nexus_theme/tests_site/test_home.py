"""Site-backed checks of the Nexus home page.

Needs a running site — `bench --site <site> run-tests --app nexus_theme` —
like the rest of tests_site. The pure rules (tile shaping, tints, the
greeting hours) are covered without a site in nexus_theme/tests; these pin
what only shows against a real database: which workspaces a restricted
user is given, the to-do badge, and when boot hands the Desk's landing to
the page.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from nexus_theme import api
from nexus_theme.nexus_theme.doctype.theme_settings.theme_settings import (
	DEFAULTS,
	clear_settings_cache,
)
from nexus_theme.utils.home import HOME_PAGE

ADMIN = "Administrator"
ROLE_PLAIN = "NXH Plain Desk"
ROLE_GATED = "NXH Gated Desk"
WORKSPACE = "NXH Gated Workspace"
USER_PLAIN = "nxh-plain@example.com"
USER_GATED = "nxh-gated@example.com"
HOME_FIELDS = ("use_nexus_home", "home_show_greeting", "home_show_shortcuts", "home_layout")


def _drop_user(email):
	if frappe.db.exists("User", email):
		frappe.db.delete("ToDo", {"allocated_to": email})
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)


def _make_user(email, role):
	_drop_user(email)
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": "Nexus",
			"last_name": "Tester",
			"send_welcome_email": 0,
			"roles": [{"role": role}],
		}
	).insert(ignore_permissions=True)


class TestHomeData(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user(ADMIN)
		for role in (ROLE_PLAIN, ROLE_GATED):
			if not frappe.db.exists("Role", role):
				frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
					ignore_permissions=True
				)
		if frappe.db.exists("Workspace", WORKSPACE):
			frappe.delete_doc("Workspace", WORKSPACE, force=True, ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Workspace",
				"label": WORKSPACE,
				"title": WORKSPACE,
				"public": 1,
				"module": "Nexus Theme",
				"content": "[]",
				"roles": [{"role": ROLE_GATED}],
			}
		).insert(ignore_permissions=True)
		_make_user(USER_PLAIN, ROLE_PLAIN)
		_make_user(USER_GATED, ROLE_GATED)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user(ADMIN)
		for email in (USER_PLAIN, USER_GATED):
			_drop_user(email)
		if frappe.db.exists("Workspace", WORKSPACE):
			frappe.delete_doc("Workspace", WORKSPACE, force=True, ignore_permissions=True)
		super().tearDownClass()

	def setUp(self):
		frappe.set_user(ADMIN)
		for email in (USER_PLAIN, USER_GATED, ADMIN):
			api.clear_home_cache(email)

	def tearDown(self):
		frappe.set_user(ADMIN)

	def _tiles_for(self, user):
		frappe.set_user(user)
		try:
			api.clear_home_cache(user)
			return {t["name"]: t for t in api.get_home_data()["tiles"]}
		finally:
			frappe.set_user(ADMIN)

	def test_only_workspaces_the_user_may_open_are_tiles(self):
		plain = self._tiles_for(USER_PLAIN)
		gated = self._tiles_for(USER_GATED)
		self.assertNotIn(WORKSPACE, plain)
		self.assertIn(WORKSPACE, gated)

		# Nothing beyond what the Desk's own sidebar builder offers them.
		frappe.set_user(USER_PLAIN)
		try:
			sidebar = {p.get("name") for p in api._workspace_pages()}
		finally:
			frappe.set_user(ADMIN)
		self.assertLessEqual(set(plain), sidebar)

	def test_hidden_workspaces_are_left_out(self):
		frappe.db.set_value("Workspace", WORKSPACE, "is_hidden", 1)
		try:
			self.assertNotIn(WORKSPACE, self._tiles_for(USER_GATED))
		finally:
			frappe.db.set_value("Workspace", WORKSPACE, "is_hidden", 0)

	def test_badge_counts_open_todos_in_the_workspace_module(self):
		self.assertEqual(self._tiles_for(USER_GATED)[WORKSPACE]["count"], 0)

		made = []
		for status in ("Open", "Open", "Closed"):
			todo = frappe.get_doc(
				{
					"doctype": "ToDo",
					"description": "Nexus home badge",
					"allocated_to": USER_GATED,
					"reference_type": "Theme Definition",
					"status": status,
				}
			).insert(ignore_permissions=True)
			made.append(todo.name)
		# One for someone else, which must not count.
		other = frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": "Nexus home badge",
				"allocated_to": USER_PLAIN,
				"reference_type": "Theme Definition",
				"status": "Open",
			}
		).insert(ignore_permissions=True)
		made.append(other.name)

		try:
			data_tiles = self._tiles_for(USER_GATED)
			# Theme Definition belongs to the Nexus Theme module, as does
			# the test workspace.
			self.assertEqual(data_tiles[WORKSPACE]["count"], 2)
			frappe.set_user(USER_GATED)
			try:
				api.clear_home_cache(USER_GATED)
				self.assertEqual(api.get_home_data()["open_todos"], 2)
			finally:
				frappe.set_user(ADMIN)
		finally:
			for name in made:
				frappe.delete_doc("ToDo", name, force=True, ignore_permissions=True)

	def test_greeting_name_is_the_first_name(self):
		frappe.set_user(USER_GATED)
		try:
			self.assertEqual(api.get_home_data()["greeting_name"], "Nexus")
		finally:
			frappe.set_user(ADMIN)

	def test_results_are_cached_per_user_for_a_minute(self):
		frappe.set_user(USER_GATED)
		try:
			first = api.get_home_data()
			with patch.object(api, "_build_home_data", side_effect=AssertionError("not cached")):
				second = api.get_home_data()
			self.assertEqual(first["tiles"], second["tiles"])
		finally:
			frappe.set_user(ADMIN)

	def test_guests_and_website_users_are_refused(self):
		frappe.set_user("Guest")
		try:
			self.assertRaises(frappe.PermissionError, api.get_home_data)
		finally:
			frappe.set_user(ADMIN)


class TestHomeBoot(FrappeTestCase):
	def setUp(self):
		frappe.set_user(ADMIN)
		doc = frappe.get_doc("Theme Settings")
		self._prev = {f: doc.get(f) for f in HOME_FIELDS}

	def tearDown(self):
		frappe.set_user(ADMIN)
		self._set(**self._prev)

	def _set(self, **values):
		doc = frappe.get_doc("Theme Settings")
		for key, value in values.items():
			doc.set(key, value)
		doc.save(ignore_permissions=True)
		clear_settings_cache()

	def _boot(self, home_page="desktop"):
		bootinfo = frappe._dict(home_page=home_page, docs=[])
		api._apply_home_boot(bootinfo)
		return bootinfo

	def test_settings_defaults_leave_the_page_off(self):
		self.assertEqual(DEFAULTS["use_nexus_home"], 0)
		self.assertEqual(DEFAULTS["home_show_greeting"], 1)
		self.assertEqual(DEFAULTS["home_show_shortcuts"], 1)
		self.assertEqual(DEFAULTS["home_layout"], "Grid")

	def test_unset_values_read_as_their_defaults(self):
		with patch.object(api, "_settings", return_value={k: None for k in HOME_FIELDS}):
			home = api._home_settings()
		self.assertEqual(home, {"enabled": 0, "show_greeting": 1, "show_shortcuts": 1, "layout": "grid"})

	def test_off_leaves_frappes_home_alone(self):
		self._set(use_nexus_home=0)
		for original in ("desktop", "Workspaces"):
			bootinfo = self._boot(original)
			self.assertEqual(bootinfo.home_page, original)
			self.assertEqual(bootinfo.nexus_home["enabled"], 0)
			self.assertEqual(bootinfo.nexus_home["active"], 0)
			self.assertEqual(bootinfo.docs, [])

	def test_on_takes_the_landing_and_ships_the_page(self):
		self._set(use_nexus_home=1, home_layout="Compact list", home_show_greeting=0)
		bootinfo = self._boot("desktop")
		self.assertEqual(bootinfo.home_page, HOME_PAGE)
		self.assertEqual(bootinfo.nexus_home["active"], 1)
		self.assertEqual(bootinfo.nexus_home["frappe_home"], "desktop")
		self.assertEqual(bootinfo.nexus_home["layout"], "list")
		self.assertEqual(bootinfo.nexus_home["show_greeting"], 0)
		self.assertEqual([d.get("name") for d in bootinfo.docs], [HOME_PAGE])
		self.assertTrue(bootinfo.docs[0].get("script"))

	def test_the_boot_hook_applies_it(self):
		self.assertIn("nexus_theme.api.extend_boot_session", frappe.get_hooks("boot_session"))
		self._set(use_nexus_home=1)
		bootinfo = frappe._dict(home_page="desktop", docs=[])
		api.extend_boot_session(bootinfo)
		self.assertEqual(bootinfo.home_page, HOME_PAGE)
		self._set(use_nexus_home=0)
		bootinfo = frappe._dict(home_page="desktop", docs=[])
		api.extend_boot_session(bootinfo)
		self.assertEqual(bootinfo.home_page, "desktop")

	def test_never_before_setup_is_complete(self):
		self._set(use_nexus_home=1)
		with patch("frappe.is_setup_complete", return_value=False):
			bootinfo = self._boot("setup-wizard")
		self.assertEqual(bootinfo.home_page, "setup-wizard")
		self.assertEqual(bootinfo.nexus_home["active"], 0)
		# Nor when boot still asks for the wizard for any other reason.
		self.assertEqual(self._boot("setup-wizard").home_page, "setup-wizard")

	def test_never_for_guests(self):
		self._set(use_nexus_home=1)
		frappe.set_user("Guest")
		try:
			bootinfo = self._boot("desktop")
		finally:
			frappe.set_user(ADMIN)
		self.assertEqual(bootinfo.home_page, "desktop")
