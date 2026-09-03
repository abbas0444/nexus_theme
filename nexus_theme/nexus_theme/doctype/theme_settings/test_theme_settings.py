import frappe
from frappe.tests.utils import FrappeTestCase

from nexus_theme.nexus_theme.doctype.theme_settings.theme_settings import (
	DEFAULTS,
	get_settings,
)


class TestThemeSettings(FrappeTestCase):
	def tearDown(self):
		# Leave the site as we found it — these settings are global.
		doc = frappe.get_single("Theme Settings")
		doc.restrict_theme_choice = 0
		doc.allowed_themes = []
		doc.site_default_theme = None
		doc.allow_custom_themes = 1
		doc.allow_public_sharing = 1
		doc.allow_user_sounds = 1
		doc.flags.ignore_permissions = True
		doc.save()

	def test_get_settings_returns_every_default_key(self):
		settings = get_settings()
		for key in DEFAULTS:
			self.assertIn(key, settings)

	def test_defaults_are_permissive(self):
		# A site that never opens this page must behave as it did before the
		# DocType existed.
		self.assertEqual(DEFAULTS["allow_custom_themes"], 1)
		self.assertEqual(DEFAULTS["allow_public_sharing"], 1)
		self.assertEqual(DEFAULTS["allow_user_sounds"], 1)
		self.assertEqual(DEFAULTS["restrict_theme_choice"], 0)
		self.assertIsNone(DEFAULTS["site_default_theme"])

	def test_restrict_requires_a_list(self):
		doc = frappe.get_single("Theme Settings")
		doc.restrict_theme_choice = 1
		doc.allowed_themes = []
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_site_default_must_be_allowed_when_restricted(self):
		themes = frappe.get_all("Theme Definition", filters={"is_default": 1}, limit=2)
		if len(themes) < 2:
			self.skipTest("needs two default themes")
		doc = frappe.get_single("Theme Settings")
		doc.restrict_theme_choice = 1
		doc.allowed_themes = []
		doc.append("allowed_themes", {"theme": themes[0].name})
		doc.site_default_theme = themes[1].name
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_settings_cache_reflects_a_save(self):
		doc = frappe.get_single("Theme Settings")
		doc.allow_custom_themes = 0
		doc.flags.ignore_permissions = True
		doc.save()
		self.assertEqual(get_settings()["allow_custom_themes"], 0)
