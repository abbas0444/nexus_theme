"""Unit tests for the CSS-injection guard on theme style values.

Pure-logic tests — no database or Frappe site required.
"""

import unittest

from nexus_theme.utils.css_safety import (
	COLOR_FIELDS,
	STYLE_FIELDS,
	is_safe_value,
	sanitize_overrides,
)


class TestColorValidation(unittest.TestCase):
	def test_accepts_valid_hex_forms(self):
		for ok in ("#fff", "#ffff", "#1a2b3c", "#1a2b3cff", "  #ABCDEF  "):
			self.assertTrue(is_safe_value("bg_primary", ok), ok)

	def test_rejects_non_hex_color(self):
		for bad in (
			"red",
			"url(https://evil.example/beacon)",
			"#1a2b3c; background:url(https://evil)",
			"#12345",
			"rgb(0,0,0)",
		):
			self.assertFalse(is_safe_value("bg_primary", bad), bad)

	def test_every_color_field_is_validated(self):
		for field in COLOR_FIELDS:
			self.assertTrue(is_safe_value(field, "#000000"), field)
			self.assertFalse(is_safe_value(field, "url(x)"), field)

	def test_empty_value_is_safe(self):
		# An empty field falls back to a client default — nothing is injected.
		self.assertTrue(is_safe_value("bg_primary", ""))
		self.assertTrue(is_safe_value("bg_primary", None))


class TestStyleValidation(unittest.TestCase):
	def test_accepts_real_font_stacks(self):
		for ok in (
			'"Inter", system-ui, sans-serif',
			'-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
			'"JetBrains Mono", ui-monospace, monospace',
		):
			self.assertTrue(is_safe_value("font_family", ok), ok)

	def test_rejects_font_family_breakout(self):
		for bad in (
			"Inter; background:url(https://evil)",
			"Inter} html{display:none",
			"Inter:expression(alert(1))",
		):
			self.assertFalse(is_safe_value("font_family", bad), bad)

	def test_size_duration_radius_patterns(self):
		self.assertTrue(is_safe_value("font_size_base", "14px"))
		self.assertTrue(is_safe_value("transition_duration", "150ms"))
		self.assertTrue(is_safe_value("border_radius", "8px"))
		self.assertFalse(is_safe_value("font_size_base", "14px;}html{x:y"))
		self.assertFalse(is_safe_value("transition_duration", "150"))

	def test_unknown_field_is_unsafe(self):
		# A field we do not recognise must never be treated as injectable.
		self.assertFalse(is_safe_value("not_a_real_field", "#000000"))


class TestSanitizeOverrides(unittest.TestCase):
	def test_drops_unsafe_entries_keeps_safe(self):
		dirty = {
			"bg_primary": "#101820",
			"text_primary": "url(https://evil.example/x)",
			"font_family": '"Inter", sans-serif',
			"border_radius": "8px;}html{x",
			"unknown_key": "anything",
		}
		clean = sanitize_overrides(dirty)
		self.assertEqual(clean, {"bg_primary": "#101820", "font_family": '"Inter", sans-serif'})

	def test_non_dict_input_yields_empty(self):
		self.assertEqual(sanitize_overrides(None), {})
		self.assertEqual(sanitize_overrides("not a dict"), {})

	def test_hover_lift_is_coerced_to_flag(self):
		self.assertEqual(sanitize_overrides({"enable_hover_lift": "yes"}), {"enable_hover_lift": 1})
		self.assertEqual(sanitize_overrides({"enable_hover_lift": 0}), {"enable_hover_lift": 0})

	def test_style_fields_tuple_is_exposed(self):
		self.assertIn("font_family", STYLE_FIELDS)


if __name__ == "__main__":
	unittest.main()
