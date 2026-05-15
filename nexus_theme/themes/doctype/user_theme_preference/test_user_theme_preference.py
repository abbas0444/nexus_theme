import frappe
from frappe.tests.utils import FrappeTestCase


class TestUserThemePreference(FrappeTestCase):
	def test_invalid_overrides_json_is_rejected(self):
		doc = frappe.new_doc("User Theme Preference")
		doc.overrides_json = "{not valid json"
		self.assertRaises(frappe.ValidationError, doc.validate)

	def test_non_object_overrides_json_is_rejected(self):
		doc = frappe.new_doc("User Theme Preference")
		doc.overrides_json = "[1, 2, 3]"
		self.assertRaises(frappe.ValidationError, doc.validate)

	def test_empty_overrides_defaults_to_empty_object(self):
		doc = frappe.new_doc("User Theme Preference")
		doc.overrides_json = ""
		doc.validate()
		self.assertEqual(doc.overrides_json, "{}")

	def test_valid_overrides_json_is_accepted(self):
		doc = frappe.new_doc("User Theme Preference")
		doc.overrides_json = '{"accent": "#6366f1"}'
		doc.validate()
		self.assertEqual(doc.overrides_json, '{"accent": "#6366f1"}')
