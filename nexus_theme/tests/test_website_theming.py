"""Unit tests for the login/website CSS variable injection.

Pure-logic tests — no database or Frappe site required. They cover the one
part of website.py that must never be wrong: the string that gets written
verbatim into every public page's <head>.
"""

import unittest

from nexus_theme.utils.web_css import VAR_MAP, brand_color, css_url
from nexus_theme.utils.web_css import theme_css_rules as _theme_style_block


def theme(**overrides):
	base = {
		"bg_primary": "#ffffff",
		"bg_surface": "#f6f8fa",
		"text_primary": "#1f2328",
		"accent": "#0969da",
		"font_family": '"Inter", sans-serif',
		"font_size_base": "14px",
		"border_radius": "6px",
		"transition_duration": "150ms",
		"font_weight_base": 400,
		"is_dark": 0,
	}
	base.update(overrides)
	return base


class TestThemeStyleBlock(unittest.TestCase):
	def test_emits_css_variables(self):
		out = _theme_style_block(theme())
		self.assertIn("--theme-bg-primary:#ffffff", out)
		self.assertIn("--theme-accent:#0969da", out)
		self.assertIn(":root{", out)
		self.assertNotIn("<style", out)  # colocated_css is wrapped by Frappe

	def test_empty_theme_emits_nothing(self):
		# No declarations means no <style> tag at all, so a misconfigured
		# site renders stock Frappe rather than an empty style block.
		self.assertEqual(_theme_style_block({}), "")

	def test_unsafe_color_is_dropped(self):
		out = _theme_style_block(theme(bg_primary="url(https://evil.example/x)"))
		self.assertNotIn("evil.example", out)
		self.assertNotIn("--theme-bg-primary", out)

	def test_unsafe_font_family_is_dropped(self):
		out = _theme_style_block(theme(font_family="Inter; background:url(https://evil)"))
		self.assertNotIn("evil", out)
		self.assertNotIn("--theme-font-family", out)

	def test_declaration_breakout_cannot_escape_the_block(self):
		# The killer case: a value containing } would end the :root rule and
		# let everything after it become new CSS.
		out = _theme_style_block(theme(bg_primary="#fff}html{display:none"))
		self.assertNotIn("display:none", out)

	def test_non_numeric_font_weight_is_dropped(self):
		out = _theme_style_block(theme(font_weight_base="400;x:y"))
		self.assertNotIn("--theme-font-weight-base", out)

	def test_color_scheme_follows_is_dark(self):
		self.assertIn("color-scheme:dark", _theme_style_block(theme(is_dark=1)))
		self.assertIn("color-scheme:light", _theme_style_block(theme(is_dark=0)))

	def test_var_map_matches_the_desk_mapping(self):
		# website.py mirrors VAR_MAP in theme_manager.js. If the Desk gains a
		# token and the website does not, branding silently diverges.
		from pathlib import Path

		js = (Path(__file__).resolve().parent.parent / "public" / "js" / "theme_manager.js").read_text()
		for field, css_var in VAR_MAP.items():
			self.assertIn(field, js, f"{field} missing from theme_manager.js")
			self.assertIn(css_var, js, f"{css_var} missing from theme_manager.js")


class TestBrandColor(unittest.TestCase):
	"""The login panel wears the colour the Desk is known by."""

	def test_a_solid_or_gradient_sidebar_is_the_brand(self):
		for style in ("Solid", "Gradient", "gradient"):
			self.assertEqual(brand_color(theme(sidebar_style=style, sidebar_bg="#1b1030")), "#1b1030")

	def test_an_auto_sidebar_colour_is_the_accent(self):
		self.assertEqual(brand_color(theme(sidebar_style="Solid", sidebar_bg="")), "#0969da")

	def test_plain_and_tinted_have_no_brand_block(self):
		for style in ("Plain", "Tinted", "", None):
			self.assertIsNone(brand_color(theme(sidebar_style=style, sidebar_bg="#1b1030")))

	def test_an_unsafe_value_never_becomes_the_brand(self):
		self.assertIsNone(brand_color(theme(sidebar_style="Solid", sidebar_bg="red;}body{x")))

	def test_the_style_block_carries_it_only_when_there_is_one(self):
		self.assertIn(
			"--theme-brand:#1b1030", _theme_style_block(theme(sidebar_style="Gradient", sidebar_bg="#1b1030"))
		)
		self.assertNotIn("--theme-brand", _theme_style_block(theme(sidebar_style="Tinted")))


class TestCssUrl(unittest.TestCase):
	def test_quotes_a_plain_path(self):
		self.assertEqual(css_url("/files/bg.png"), '"/files/bg.png"')
		self.assertEqual(css_url("  /files/bg.png  "), '"/files/bg.png"')

	def test_keeps_characters_html_escaping_broke(self):
		# escape_html turned these into &amp; and &#x27;, and the browser
		# fetched a file that did not exist.
		self.assertEqual(css_url("/files/a&b.png"), '"/files/a&b.png"')
		self.assertEqual(css_url("/files/it's.png"), '"/files/it\'s.png"')
		self.assertEqual(css_url("/files/bg.png?v=1&x=2"), '"/files/bg.png?v=1&x=2"')

	def test_escapes_quotes_and_backslashes(self):
		self.assertEqual(css_url('/files/a"b.png'), '"/files/a\\"b.png"')
		self.assertEqual(css_url("/files/a\\b.png"), '"/files/a\\\\b.png"')

	def test_refuses_what_cannot_be_made_safe(self):
		for bad in (
			"",
			"   ",
			None,
			42,
			"/files/x.png\n}body{display:none}",
			"/files/x.png</style><script>alert(1)</script>",
			"/files/x\t.png",
			"/files/x\x00.png",
		):
			self.assertIsNone(css_url(bad), repr(bad))


if __name__ == "__main__":
	unittest.main()
