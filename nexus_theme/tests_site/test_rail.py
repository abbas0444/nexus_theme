"""Site-backed checks of the mini rail (collapsed sidebar) API.

Needs a running site — `bench --site <site> run-tests --app nexus_theme` —
like the rest of tests_site. Which spellings count as collapsed is covered
without a site in nexus_theme/tests/test_rail.py; these pin what only shows
up against a real database: the row that is created or removed, how the
choice sits beside the theme and the density on it, and what boot hands the
Desk.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from nexus_theme import api
from nexus_theme.nexus_theme.doctype.theme_settings.theme_settings import (
	clear_settings_cache,
)

ADMIN = "Administrator"


def _bundled(is_dark: int) -> str | None:
	return frappe.db.get_value("Theme Definition", {"is_default": 1, "is_dark": is_dark}, "name")


class TestSidebarRailApi(FrappeTestCase):
	def setUp(self):
		frappe.set_user(ADMIN)
		s = frappe.get_doc("Theme Settings")
		self._prev = s.site_default_theme
		self._site_default(None)
		self._drop_pref()
		self._made: list[str] = []

	def tearDown(self):
		frappe.set_user(ADMIN)
		self._drop_pref()
		self._site_default(self._prev)
		for name in self._made:
			if frappe.db.exists("Theme Definition", name):
				frappe.db.delete("User Theme Preference", {"active_theme": name})
				frappe.delete_doc("Theme Definition", name, force=True, ignore_permissions=True)

	def _site_default(self, theme):
		doc = frappe.get_doc("Theme Settings")
		doc.site_default_theme = theme
		doc.save(ignore_permissions=True)
		clear_settings_cache()

	def _drop_pref(self):
		name = frappe.db.exists("User Theme Preference", {"user": ADMIN})
		if name:
			frappe.delete_doc("User Theme Preference", name, force=True, ignore_permissions=True)

	def _row(self):
		name = frappe.db.exists("User Theme Preference", {"user": ADMIN})
		return frappe.get_doc("User Theme Preference", name) if name else None

	# ------------------------------------------------------------------
	# Validation
	# ------------------------------------------------------------------

	def test_nonsense_is_refused_and_nothing_is_stored(self):
		for bad in ("maybe", "2", 2, "collapse;"):
			with self.subTest(collapsed=bad):
				self.assertRaises(frappe.ValidationError, api.set_sidebar_collapsed, bad)
		self.assertIsNone(self._row())

	def test_the_usual_spellings_are_taken(self):
		for given, want in ((1, 1), ("true", 1), ("0", 0), ("collapsed", 1), (False, 0)):
			with self.subTest(collapsed=given):
				self.assertEqual(api.set_sidebar_collapsed(given)["collapsed"], want)
				self.assertEqual(api.get_sidebar_collapsed(), {"collapsed": want})

	def test_the_check_is_kept_to_zero_or_one(self):
		"""The row can also arrive through /api/resource or the form."""
		doc = frappe.new_doc("User Theme Preference")
		doc.user = ADMIN
		doc.sidebar_collapsed = 7
		doc.insert()
		self.assertEqual(self._row().sidebar_collapsed, 1)

	# ------------------------------------------------------------------
	# A row with only this on it
	# ------------------------------------------------------------------

	def test_a_row_may_hold_only_a_collapsed_sidebar(self):
		api.set_sidebar_collapsed(1)

		row = self._row()
		self.assertEqual(row.sidebar_collapsed, 1)
		self.assertFalse(row.active_theme)
		self.assertFalse(row.use_frappe_theme)
		self.assertFalse(row.density)

		# Reads as "never chose" for the theme, site default included.
		got = api.get_active_theme()
		self.assertIsNone(got["theme"])
		self.assertEqual(got["sidebar_collapsed"], 1)
		dark = _bundled(1)
		if dark:
			self._site_default(dark)
			got = api.get_active_theme()
			self.assertEqual(got["source"], "site_default")
			self.assertEqual(got["sidebar_collapsed"], 1)

	def test_an_expanded_sidebar_alone_is_still_an_empty_row(self):
		doc = frappe.new_doc("User Theme Preference")
		doc.user = ADMIN
		doc.sidebar_collapsed = 0
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_expanding_with_nothing_stored_writes_nothing(self):
		self.assertEqual(api.set_sidebar_collapsed(0), {"ok": True, "collapsed": 0})
		self.assertIsNone(self._row())

	def test_expanding_a_row_that_holds_nothing_else_removes_it(self):
		api.set_sidebar_collapsed(1)
		self.assertIsNotNone(self._row())
		api.set_sidebar_collapsed(0)
		self.assertIsNone(self._row())
		self.assertEqual(api.get_sidebar_collapsed(), {"collapsed": 0})

	# ------------------------------------------------------------------
	# Beside the theme and the density
	# ------------------------------------------------------------------

	def test_the_theme_and_the_rail_leave_each_other_alone(self):
		light = _bundled(0)
		if not light:
			self.skipTest("no bundled light theme on this site")
		api.set_sidebar_collapsed(1)
		api.set_active_theme(light)
		got = api.get_active_theme()
		self.assertEqual(got["theme"]["name"], light)
		self.assertEqual(got["sidebar_collapsed"], 1)

		# Expanding on a row with a theme keeps the row and the theme.
		api.set_sidebar_collapsed(0)
		row = self._row()
		self.assertEqual(row.active_theme, light)
		self.assertEqual(row.sidebar_collapsed, 0)

	def test_opting_out_to_frappes_theme_keeps_the_rail(self):
		api.set_sidebar_collapsed(1)
		api.clear_active_theme()
		got = api.get_active_theme()
		self.assertEqual(got["source"], "frappe")
		self.assertEqual(got["sidebar_collapsed"], 1)

	def test_clearing_the_density_keeps_a_row_that_holds_the_rail(self):
		api.set_density("compact")
		api.set_sidebar_collapsed(1)
		api.set_density("")
		row = self._row()
		self.assertIsNotNone(row)
		self.assertEqual(row.sidebar_collapsed, 1)
		self.assertIsNone(row.density)

	def test_expanding_keeps_a_row_that_holds_a_density(self):
		api.set_density("spacious")
		api.set_sidebar_collapsed(1)
		api.set_sidebar_collapsed(0)
		row = self._row()
		self.assertIsNotNone(row)
		self.assertEqual(row.density, "Spacious")

	def test_deleting_the_theme_in_use_keeps_the_rail(self):
		base = _bundled(0)
		if not base:
			self.skipTest("no bundled light theme on this site")
		theme = frappe.copy_doc(frappe.get_doc("Theme Definition", base))
		theme.theme_key = "nxt-test-rail-keep"
		theme.theme_name = "Nxt Test Rail Keep"
		theme.is_default = 0
		theme.is_public = 0
		theme.owner_user = ADMIN
		theme.insert(ignore_permissions=True)
		self._made.append(theme.name)

		api.set_active_theme(theme.name)
		api.set_sidebar_collapsed(1)
		api.delete_custom_theme(theme.name)

		row = self._row()
		self.assertIsNotNone(row)
		self.assertFalse(row.active_theme)
		self.assertEqual(row.sidebar_collapsed, 1)

	# ------------------------------------------------------------------
	# Boot
	# ------------------------------------------------------------------

	def test_boot_carries_the_choice(self):
		bootinfo = {}
		api.extend_boot_session(bootinfo)
		self.assertEqual(bootinfo["nexus_sidebar_collapsed"], 0)
		self.assertEqual(bootinfo["active_theme"]["sidebar_collapsed"], 0)

		api.set_sidebar_collapsed(1)
		bootinfo = {}
		api.extend_boot_session(bootinfo)
		self.assertEqual(bootinfo["nexus_sidebar_collapsed"], 1)
		self.assertEqual(bootinfo["active_theme"]["sidebar_collapsed"], 1)
