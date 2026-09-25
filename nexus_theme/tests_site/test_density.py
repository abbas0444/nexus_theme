"""Site-backed checks of the density API.

Needs a running site — `bench --site <site> run-tests --app nexus_theme` —
like the rest of tests_site. The pure rules (which spellings name a mode,
the resolution order) are covered without a site in nexus_theme/tests;
these pin what only shows up against a real database: the row that is
created or removed, how the density sits beside the theme on it, and
what boot hands the Desk.
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


class TestDensityApi(FrappeTestCase):
	def setUp(self):
		frappe.set_user(ADMIN)
		s = frappe.get_doc("Theme Settings")
		self._prev = (s.default_density, s.site_default_theme)
		self._govern("Comfortable", None)
		self._drop_pref()
		self._made: list[str] = []

	def tearDown(self):
		frappe.set_user(ADMIN)
		self._drop_pref()
		self._govern(*self._prev)
		for name in self._made:
			if frappe.db.exists("Theme Definition", name):
				frappe.db.delete("User Theme Preference", {"active_theme": name})
				frappe.delete_doc("Theme Definition", name, force=True, ignore_permissions=True)

	def _govern(self, default_density, site_default_theme):
		doc = frappe.get_doc("Theme Settings")
		doc.default_density = default_density
		doc.site_default_theme = site_default_theme
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

	def test_only_the_three_modes_are_accepted(self):
		for bad in ("dense", "Automatic", "compact;", "roomy"):
			with self.subTest(density=bad):
				self.assertRaises(frappe.ValidationError, api.set_density, bad)
		self.assertIsNone(self._row())

	def test_keys_and_labels_are_both_taken_and_stored_as_the_label(self):
		for given, label in (
			("compact", "Compact"),
			("Spacious", "Spacious"),
			("COMFORTABLE", "Comfortable"),
		):
			with self.subTest(density=given):
				got = api.set_density(given)
				self.assertEqual(got["density"], label.lower())
				self.assertEqual(got["source"], "user")
				self.assertEqual(self._row().density, label)

	# ------------------------------------------------------------------
	# Persistence beside the theme
	# ------------------------------------------------------------------

	def test_a_density_needs_no_theme(self):
		"""The row is created with only a density, and reads as "never
		chose" for the theme — site default included."""
		api.set_density("compact")

		row = self._row()
		self.assertEqual(row.density, "Compact")
		self.assertFalse(row.active_theme)
		self.assertFalse(row.use_frappe_theme)

		got = api.get_active_theme()
		self.assertIsNone(got["theme"])
		self.assertEqual(got["density"], "compact")

		dark = _bundled(1)
		if dark:
			self._govern("Comfortable", dark)
			got = api.get_active_theme()
			self.assertEqual(got["source"], "site_default")
			self.assertEqual(got["theme"]["name"], dark)
			self.assertEqual(got["density"], "compact")

	def test_applying_a_theme_keeps_the_density_and_vice_versa(self):
		light = _bundled(0)
		if not light:
			self.skipTest("no bundled light theme on this site")

		api.set_density("spacious")
		api.set_active_theme(light)
		got = api.get_active_theme()
		self.assertEqual(got["theme"]["name"], light)
		self.assertEqual(got["density"], "spacious")

		api.set_density("compact")
		got = api.get_active_theme()
		self.assertEqual(got["theme"]["name"], light)
		self.assertEqual(got["density"], "compact")

	def test_opting_out_to_frappes_theme_keeps_the_density(self):
		api.set_density("compact")
		api.clear_active_theme()
		got = api.get_active_theme()
		self.assertEqual(got["source"], "frappe")
		self.assertEqual(got["density"], "compact")
		self.assertEqual(api.get_density(), {"density": "compact", "source": "user"})

	def test_deleting_the_theme_in_use_keeps_the_density(self):
		"""Releasing a theme about to be deleted used to drop the whole
		preference row; the density on it is the person's own choice and
		has nothing to do with the theme."""
		theme = frappe.copy_doc(frappe.get_doc("Theme Definition", _bundled(0)))
		theme.theme_key = "nxt-test-density-keep"
		theme.theme_name = "Nxt Test Density Keep"
		theme.is_default = 0
		theme.is_public = 0
		theme.owner_user = ADMIN
		theme.insert(ignore_permissions=True)
		self._made.append(theme.name)

		api.set_active_theme(theme.name)
		api.set_density("spacious")
		api.delete_custom_theme(theme.name)

		row = self._row()
		self.assertIsNotNone(row)
		self.assertFalse(row.active_theme)
		self.assertEqual(row.density, "Spacious")
		got = api.get_active_theme()
		self.assertIsNone(got["theme"])
		self.assertEqual(got["density"], "spacious")

	def test_clearing_the_density_on_a_row_with_nothing_else_removes_it(self):
		api.set_density("compact")
		self.assertIsNotNone(self._row())

		got = api.set_density("")
		self.assertIsNone(self._row())
		self.assertEqual(got["source"], "site_default")

		# Clearing when nothing is stored is a no-op that still answers.
		got = api.set_density(None)
		self.assertIsNone(self._row())
		self.assertEqual(got["density"], "comfortable")

	def test_clearing_the_density_on_a_row_with_a_theme_keeps_the_theme(self):
		light = _bundled(0)
		if not light:
			self.skipTest("no bundled light theme on this site")
		api.set_active_theme(light)
		api.set_density("compact")
		api.set_density(None)
		row = self._row()
		self.assertEqual(row.active_theme, light)
		self.assertIsNone(row.density)
		self.assertEqual(api.get_density()["source"], "site_default")

	# ------------------------------------------------------------------
	# Resolution order: user, then the site's default, then Comfortable
	# ------------------------------------------------------------------

	def test_resolution_order(self):
		# Nobody chose anything: the site's own default, which is Comfortable.
		self.assertEqual(api.get_density(), {"density": "comfortable", "source": "site_default"})

		# An admin picks a site default; users without one follow it.
		self._govern("Spacious", None)
		self.assertEqual(api.get_density(), {"density": "spacious", "source": "site_default"})

		# The user's own choice beats it.
		api.set_density("compact")
		self.assertEqual(api.get_density(), {"density": "compact", "source": "user"})

		# Letting go of the choice goes back to following the site.
		api.set_density("")
		self.assertEqual(api.get_density(), {"density": "spacious", "source": "site_default"})

		# A site with the default cleared falls to Comfortable.
		self._govern(None, None)
		self.assertEqual(api.get_density(), {"density": "comfortable", "source": "default"})

	def test_boot_carries_the_resolved_density(self):
		self._govern("Spacious", None)
		bootinfo = {}
		api.extend_boot_session(bootinfo)
		self.assertEqual(bootinfo["nexus_density"], {"density": "spacious", "source": "site_default"})
		self.assertEqual(bootinfo["active_theme"]["density"], "spacious")

		api.set_density("compact")
		bootinfo = {}
		api.extend_boot_session(bootinfo)
		self.assertEqual(bootinfo["nexus_density"], {"density": "compact", "source": "user"})
		self.assertEqual(bootinfo["active_theme"]["density"], "compact")
