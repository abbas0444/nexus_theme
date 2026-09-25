"""Unit tests for the sidebar skin derivation.

Pure-logic tests — no database or Frappe site required.
"""

import unittest

from nexus_theme.utils.contrast import contrast_ratio
from nexus_theme.utils.sidebar_skin import (
	SIDEBAR_STYLES,
	normalize_style,
	resolve_sidebar,
	sidebar_contrast_failures,
)

BASE = {
	"bg_primary": "#ffffff",
	"bg_surface": "#f6f8fa",
	"text_primary": "#1f2328",
	"accent": "#0969da",
}


def theme(**values):
	out = dict(BASE)
	out.update(values)
	return out


class TestResolveSidebar(unittest.TestCase):
	def test_plain_and_unknown_resolve_to_nothing(self):
		self.assertIsNone(resolve_sidebar(theme()))
		self.assertIsNone(resolve_sidebar(theme(sidebar_style="Plain")))
		self.assertIsNone(resolve_sidebar(theme(sidebar_style="Neon")))
		self.assertEqual(normalize_style(None), "Plain")
		self.assertEqual(SIDEBAR_STYLES, ("Plain", "Tinted", "Solid", "Gradient"))

	def test_solid_defaults_to_the_accent_with_readable_text(self):
		skin = resolve_sidebar(theme(sidebar_style="Solid"))
		self.assertEqual(skin["bg"], "#0969da")
		self.assertEqual(skin["bg_end"], skin["bg"])
		# The theme's own dark text fails on the blue, so white is picked.
		self.assertEqual(skin["text"], "#ffffff")

	def test_tinted_is_a_light_wash_that_keeps_the_theme_text(self):
		skin = resolve_sidebar(theme(sidebar_style="Tinted"))
		self.assertNotEqual(skin["bg"], "#0969da")
		self.assertGreater(contrast_ratio(skin["bg"], "#000000"), 15)
		self.assertEqual(skin["text"], "#1f2328")
		# The active item is the raised page-coloured pill.
		self.assertEqual(skin["active_bg"], "#ffffff")

	def test_gradient_end_is_darker(self):
		skin = resolve_sidebar(theme(sidebar_style="Gradient"))
		self.assertNotEqual(skin["bg_end"], skin["bg"])
		self.assertLess(contrast_ratio(skin["bg_end"], "#000000"), contrast_ratio(skin["bg"], "#000000"))

	def test_explicit_colours_are_used_as_given(self):
		skin = resolve_sidebar(
			theme(
				sidebar_style="Solid",
				sidebar_bg="#111111",
				sidebar_text="#eeeeee",
				sidebar_active_bg="#333333",
			)
		)
		self.assertEqual((skin["bg"], skin["text"], skin["active_bg"]), ("#111111", "#eeeeee", "#333333"))

	def test_malformed_colour_is_treated_as_empty(self):
		skin = resolve_sidebar(theme(sidebar_style="Solid", sidebar_bg="url(x)"))
		self.assertEqual(skin["bg"], "#0969da")

	def test_derived_active_item_keeps_the_text_readable(self):
		for bg in ("#0969da", "#4f46e5", "#0f766e", "#4c6a92", "#1d4ed8", "#7c3aed"):
			for style in ("Solid", "Gradient"):
				skin = resolve_sidebar(theme(sidebar_style=style, sidebar_bg=bg))
				self.assertNotEqual(skin["active_bg"], skin["bg"], (bg, style))
				self.assertGreaterEqual(contrast_ratio(skin["text"], skin["active_bg"]), 4.5, (bg, style))


class TestSidebarContrastFailures(unittest.TestCase):
	def test_plain_never_fails(self):
		self.assertEqual(sidebar_contrast_failures(theme(sidebar_text="#ffffff")), [])

	def test_auto_text_passes_on_a_strong_colour(self):
		self.assertEqual(sidebar_contrast_failures(theme(sidebar_style="Gradient")), [])

	def test_bad_explicit_text_is_reported(self):
		failures = sidebar_contrast_failures(
			theme(sidebar_style="Solid", sidebar_bg="#0969da", sidebar_text="#6699ff")
		)
		self.assertIn("sidebar_bg", [f[0] for f in failures])

	def test_gradient_end_is_judged_too(self):
		# Dark text that reads on the light start but not the darker end.
		failures = sidebar_contrast_failures(
			theme(sidebar_style="Gradient", sidebar_bg="#8ab4f8", sidebar_text="#1a1a1a")
		)
		self.assertIn("sidebar_bg (gradient end)", [f[0] for f in failures])

	def test_bad_active_item_is_reported(self):
		failures = sidebar_contrast_failures(
			theme(sidebar_style="Solid", sidebar_bg="#111111", sidebar_active_bg="#eeeeee")
		)
		self.assertEqual([f[0] for f in failures], ["sidebar_active_bg"])


if __name__ == "__main__":
	unittest.main()
