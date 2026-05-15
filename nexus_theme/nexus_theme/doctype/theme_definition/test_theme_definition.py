import frappe
from frappe.tests.utils import FrappeTestCase

from nexus_theme.themes.doctype.theme_definition.theme_definition import _SLUG_RE


class TestThemeDefinition(FrappeTestCase):
	def test_slug_regex_accepts_valid_keys(self):
		for key in ("indigo", "midnight-indigo", "theme1", "a-b-c"):
			self.assertRegex(key, _SLUG_RE)

	def test_slug_regex_rejects_invalid_keys(self):
		for key in ("Indigo", "midnight_indigo", "-leading", "with space", ""):
			self.assertIsNone(_SLUG_RE.match(key))

	def test_invalid_theme_key_is_rejected(self):
		doc = frappe.get_doc(
			{
				"doctype": "Theme Definition",
				"theme_name": "FAS Test Bad Key",
				"theme_key": "Bad_Key",
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_low_contrast_default_theme_is_blocked(self):
		# Default themes must pass WCAG AA — a grey-on-grey theme is rejected.
		doc = frappe.get_doc(
			{
				"doctype": "Theme Definition",
				"theme_name": "FAS Test Low Contrast",
				"theme_key": "nxt-test-low-contrast",
				"is_default": 1,
				"text_primary": "#777777",
				"bg_primary": "#888888",
				"bg_surface": "#888888",
				"button_text": "#777777",
				"button_bg": "#888888",
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_default_theme_cannot_be_deleted(self):
		default = frappe.get_all(
			"Theme Definition", filters={"is_default": 1}, limit=1
		)
		if not default:
			self.skipTest("no default themes present in this site")
		self.assertRaises(
			frappe.ValidationError,
			frappe.delete_doc,
			"Theme Definition",
			default[0].name,
		)
