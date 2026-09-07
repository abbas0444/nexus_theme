import frappe
from frappe.tests.utils import FrappeTestCase

from nexus_theme.api import clear_active_theme, get_active_theme, set_active_theme
from nexus_theme.nexus_theme.doctype.theme_settings.theme_settings import (
	clear_settings_cache,
)

USER = "Administrator"


def _bundled(is_dark: int) -> str | None:
	return frappe.db.get_value("Theme Definition", {"is_default": 1, "is_dark": is_dark}, "name")


class TestUserThemePreference(FrappeTestCase):
	def setUp(self):
		frappe.set_user(USER)
		settings = frappe.get_doc("Theme Settings")
		self._prev = {
			"site_default_theme": settings.site_default_theme,
			"restrict_theme_choice": settings.restrict_theme_choice,
			"allowed_themes": [r.theme for r in (settings.allowed_themes or [])],
		}
		self._govern(site_default=None, restrict=0, allowed=[])
		self._drop_pref()

	def tearDown(self):
		self._drop_pref()
		p = self._prev
		self._govern(p["site_default_theme"], p["restrict_theme_choice"], p["allowed_themes"])

	def _govern(self, site_default, restrict, allowed):
		doc = frappe.get_doc("Theme Settings")
		doc.site_default_theme = site_default
		doc.restrict_theme_choice = restrict
		doc.set("allowed_themes", [{"theme": t} for t in allowed])
		doc.save(ignore_permissions=True)
		clear_settings_cache()

	def _drop_pref(self):
		name = frappe.db.exists("User Theme Preference", {"user": USER})
		if name:
			frappe.delete_doc("User Theme Preference", name, force=True, ignore_permissions=True)

	# ------------------------------------------------------------------
	# validate()
	# ------------------------------------------------------------------

	def _doc(self, **values):
		doc = frappe.new_doc("User Theme Preference")
		doc.user = USER
		# validate() alone does not resolve links, so any name will do here.
		doc.active_theme = "github-light"
		for k, v in values.items():
			setattr(doc, k, v)
		return doc

	def test_invalid_overrides_json_is_rejected(self):
		doc = self._doc(overrides_json="{not valid json")
		self.assertRaises(frappe.ValidationError, doc.validate)

	def test_non_object_overrides_json_is_rejected(self):
		doc = self._doc(overrides_json="[1, 2, 3]")
		self.assertRaises(frappe.ValidationError, doc.validate)

	def test_empty_overrides_defaults_to_empty_object(self):
		doc = self._doc(overrides_json="")
		doc.validate()
		self.assertEqual(doc.overrides_json, "{}")

	def test_valid_overrides_json_is_accepted(self):
		doc = self._doc(overrides_json='{"accent": "#6366f1"}')
		doc.validate()
		self.assertEqual(doc.overrides_json, '{"accent": "#6366f1"}')

	def test_a_theme_is_required_unless_opting_out(self):
		doc = self._doc(active_theme=None)
		self.assertRaises(frappe.ValidationError, doc.validate)
		doc.use_frappe_theme = 1
		doc.validate()  # the opt-out row legitimately has no theme

	def test_opting_out_strips_every_theme_field(self):
		doc = self._doc(
			use_frappe_theme=1,
			theme_mode="Automatic",
			dark_theme="dracula",
			overrides_json='{"accent": "#000000"}',
		)
		doc.validate()
		self.assertFalse(doc.active_theme)
		self.assertFalse(doc.dark_theme)
		self.assertEqual(doc.theme_mode, "Single")
		self.assertEqual(doc.overrides_json, "{}")

	# ------------------------------------------------------------------
	# Resolution against the site default
	# ------------------------------------------------------------------

	def test_choosing_frappes_theme_beats_the_site_default(self):
		dark = _bundled(is_dark=1)
		if not dark:
			self.skipTest("no bundled dark theme on this site")
		self._govern(site_default=dark, restrict=0, allowed=[])

		# Never chose: the site default applies.
		self.assertEqual(get_active_theme()["source"], "site_default")

		# Chose Frappe's own theme. Deleting the row would just bring the
		# default back on the next load; the opt-out has to be recorded.
		clear_active_theme()
		got = get_active_theme()
		self.assertIsNone(got["theme"])
		self.assertEqual(got["source"], "frappe")

		# Clearing again is harmless.
		clear_active_theme()
		self.assertEqual(get_active_theme()["source"], "frappe")

	def test_applying_a_theme_ends_the_opt_out(self):
		light = _bundled(is_dark=0)
		if not light:
			self.skipTest("no bundled light theme on this site")

		clear_active_theme()
		set_active_theme(light)

		got = get_active_theme()
		self.assertEqual(got["source"], "user")
		self.assertEqual(got["theme"]["name"], light)
		self.assertFalse(frappe.db.get_value("User Theme Preference", {"user": USER}, "use_frappe_theme"))

	# ------------------------------------------------------------------
	# set_active_theme honours the same rules as the gallery
	# ------------------------------------------------------------------

	def test_cannot_apply_a_theme_off_the_allow_list(self):
		light, dark = _bundled(is_dark=0), _bundled(is_dark=1)
		if not (light and dark):
			self.skipTest("need one bundled light and one dark theme")
		self._govern(site_default=None, restrict=1, allowed=[dark])

		self.assertRaises(frappe.ValidationError, set_active_theme, light)
		set_active_theme(dark)  # the listed one is fine
		self.assertEqual(get_active_theme()["theme"]["name"], dark)

	def test_cannot_apply_another_users_private_theme(self):
		light = _bundled(is_dark=0)
		if not light:
			self.skipTest("no bundled light theme on this site")

		private = frappe.copy_doc(frappe.get_doc("Theme Definition", light))
		private.theme_key = "test-private-theme"
		private.theme_name = "Test Private Theme"
		private.is_default = 0
		private.is_public = 0
		private.owner_user = "Guest"
		private.insert(ignore_permissions=True)
		try:
			self.assertRaises(frappe.ValidationError, set_active_theme, private.name)
		finally:
			frappe.delete_doc("Theme Definition", private.name, force=True, ignore_permissions=True)
