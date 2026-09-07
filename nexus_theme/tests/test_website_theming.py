"""Unit tests for the login/website CSS variable injection.

Pure-logic tests — no database or Frappe site required. They cover the one
part of website.py that must never be wrong: the string that gets written
verbatim into every public page's <head>.
"""

import unittest

from nexus_theme.utils.web_css import VAR_MAP
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


if __name__ == "__main__":
	unittest.main()
