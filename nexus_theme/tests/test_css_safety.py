"""Unit tests for the CSS-injection guard on theme style values.

Pure-logic tests — no database or Frappe site required.
"""

import unittest

from nexus_theme.utils.css_safety import (
	COLOR_FIELDS,
	FLAG_FIELDS,
	STYLE_FIELDS,
	is_safe_value,
	sanitize_overrides,
	sanitize_overrides_blob,
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

	def test_font_family_quotes_must_pair_up(self):
		# A stray quote cannot break out of the declaration, but it opens a
		# string that never closes and the browser drops the rest of the
		# stylesheet — every rule after it on the login page, say.
		for bad in (
			"Inter'",
			"'Inter",
			'"Inter',
			'Inter", sans-serif',
			"'Inter\", sans-serif",
			"\"Segoe UI', sans-serif",
			'"Inter" Bold, sans-serif',
			",",
			"Inter,",
			'""',
		):
			self.assertFalse(is_safe_value("font_family", bad), bad)
		for ok in (
			"Inter",
			"'Inter', sans-serif",
			"Georgia, 'Iowan Old Style', \"Times New Roman\", serif",
			"  Inter , sans-serif  ",
		):
			self.assertTrue(is_safe_value("font_family", ok), ok)

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

	def test_is_dark_survives_as_flag(self):
		# A palette's polarity rides along with its colours; dropping it left
		# dark colours under data-theme="light".
		self.assertEqual(sanitize_overrides({"is_dark": 1}), {"is_dark": 1})
		self.assertEqual(sanitize_overrides({"is_dark": "1"}), {"is_dark": 1})
		self.assertEqual(sanitize_overrides({"is_dark": True}), {"is_dark": 1})
		self.assertEqual(sanitize_overrides({"is_dark": 0}), {"is_dark": 0})
		self.assertEqual(sanitize_overrides({"is_dark": "0"}), {"is_dark": 0})
		self.assertEqual(sanitize_overrides({"enable_hover_lift": "0"}), {"enable_hover_lift": 0})

	def test_blob_keeps_the_dark_half_and_cleans_it_too(self):
		# The row-level validate runs over the stored blob, where the dark
		# theme's overrides sit under one nested key. A flat sanitize would
		# drop that key and lose them on every save.
		blob = {
			"bg_primary": "#101820",
			"dark": {"bg_primary": "#000000", "text_primary": "url(https://evil.example/x)"},
		}
		self.assertEqual(
			sanitize_overrides_blob(blob),
			{"bg_primary": "#101820", "dark": {"bg_primary": "#000000"}},
		)
		# A dark half with nothing safe left in it is not written back empty.
		self.assertEqual(sanitize_overrides_blob({"dark": {"x": "y"}}), {})
		self.assertEqual(sanitize_overrides_blob({"dark": "not a dict"}), {})
		self.assertEqual(sanitize_overrides_blob(None), {})
		# Plain sanitize still refuses the key, so it can never collide.
		self.assertEqual(sanitize_overrides({"dark": {"bg_primary": "#000"}}), {})

	def test_style_fields_tuple_is_exposed(self):
		self.assertIn("font_family", STYLE_FIELDS)

	def test_sidebar_flags_are_coerced(self):
		self.assertEqual(
			sanitize_overrides({"sidebar_pattern": "1", "icon_tints": "0"}),
			{"sidebar_pattern": 1, "icon_tints": 0},
		)
		self.assertEqual(sanitize_overrides({"icon_tints": "url(x)"}), {"icon_tints": 1})

	def test_sidebar_values_survive_or_drop_like_the_rest(self):
		clean = sanitize_overrides(
			{
				"sidebar_style": "Gradient",
				"sidebar_bg": "#123456",
				"sidebar_text": "red",
				"sidebar_active_bg": "",
			}
		)
		# An empty colour is kept: it is how the Studio says "back to auto".
		self.assertEqual(
			clean,
			{"sidebar_style": "Gradient", "sidebar_bg": "#123456", "sidebar_active_bg": ""},
		)
		self.assertEqual(sanitize_overrides({"sidebar_style": "Neon"}), {})


class TestSidebarFields(unittest.TestCase):
	def test_sidebar_colours_are_colour_fields(self):
		for field in ("sidebar_bg", "sidebar_text", "sidebar_active_bg"):
			self.assertIn(field, COLOR_FIELDS)
			self.assertTrue(is_safe_value(field, "#1a2b3c"), field)
			self.assertTrue(is_safe_value(field, ""), field)
			self.assertFalse(is_safe_value(field, "#fff;background:url(x)"), field)

	def test_sidebar_style_accepts_only_the_four_styles(self):
		self.assertIn("sidebar_style", STYLE_FIELDS)
		for ok in ("Plain", "Tinted", "Solid", "Gradient", " Solid "):
			self.assertTrue(is_safe_value("sidebar_style", ok), ok)
		for bad in ("solid", "Neon", "Solid;x:y", 'Solid"', "Gradient)"):
			self.assertFalse(is_safe_value("sidebar_style", bad), bad)

	def test_flags_are_not_css_values(self):
		# A flag's value is never injected as CSS, so is_safe_value has no
		# pattern for it and refuses it — only sanitize_overrides lets it in.
		for flag in FLAG_FIELDS:
			self.assertFalse(is_safe_value(flag, "1"), flag)


if __name__ == "__main__":
	unittest.main()
