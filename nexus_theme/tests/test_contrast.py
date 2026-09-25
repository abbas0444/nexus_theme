"""Unit tests for the WCAG contrast helpers.

Pure-logic tests — no database or Frappe site required.
"""

import unittest

from nexus_theme.utils.contrast import (
	_normalize_hex,
	contrast_ratio,
	mix_hex,
	passes_aa,
	pick_text_color,
)


class TestContrast(unittest.TestCase):
	def test_normalize_expands_three_digit_hex(self):
		self.assertEqual(_normalize_hex("#fff"), "ffffff")
		self.assertEqual(_normalize_hex("000"), "000000")

	def test_normalize_strips_hash_and_whitespace(self):
		self.assertEqual(_normalize_hex("  #1E293B  "), "1E293B")

	def test_normalize_drops_the_alpha_channel(self):
		# css_safety accepts #rgba and #rrggbbaa, so the contrast check must
		# read them rather than treat them as "not a colour" and skip.
		self.assertEqual(_normalize_hex("#1e293bff"), "1e293b")
		self.assertEqual(_normalize_hex("#1e293b80"), "1e293b")
		self.assertEqual(_normalize_hex("#fff8"), "ffffff")
		self.assertEqual(_normalize_hex("#0000"), "000000")

	def test_alpha_forms_give_the_opaque_colours_ratio(self):
		self.assertAlmostEqual(contrast_ratio("#000000ff", "#ffff"), 21.0, places=2)
		self.assertAlmostEqual(
			contrast_ratio("#0f172a80", "#e2e8f0"),
			contrast_ratio("#0f172a", "#e2e8f0"),
			places=6,
		)
		self.assertFalse(passes_aa("#77777780", "#888888"))

	def test_normalize_rejects_wrong_length_hex(self):
		for bad in ("", "#12", "12345", "#1234567", "#123456789"):
			with self.assertRaises(ValueError):
				_normalize_hex(bad)

	def test_contrast_ratio_rejects_non_hex_digits(self):
		# _normalize_hex only checks length; non-hex digits surface here.
		with self.assertRaises(ValueError):
			contrast_ratio("#xyzxyz", "#ffffff")

	def test_black_on_white_is_max_ratio(self):
		# WCAG defines pure black on pure white as exactly 21:1.
		self.assertAlmostEqual(contrast_ratio("#000000", "#ffffff"), 21.0, places=2)

	def test_contrast_ratio_is_symmetric(self):
		self.assertAlmostEqual(
			contrast_ratio("#0f172a", "#e2e8f0"),
			contrast_ratio("#e2e8f0", "#0f172a"),
			places=6,
		)

	def test_same_color_has_ratio_one(self):
		self.assertAlmostEqual(contrast_ratio("#336699", "#336699"), 1.0, places=6)

	def test_passes_aa_normal_text_threshold(self):
		# Black on white clears the 4.5:1 AA bar; mid-grey on grey does not.
		self.assertTrue(passes_aa("#000000", "#ffffff"))
		self.assertFalse(passes_aa("#777777", "#888888"))

	def test_passes_aa_large_text_is_more_lenient(self):
		# A pair below 4.5:1 but above 3.0:1 fails normal AA, passes AA-large.
		fg, bg = "#8a8a8a", "#ffffff"
		ratio = contrast_ratio(fg, bg)
		self.assertGreaterEqual(ratio, 3.0)
		self.assertLess(ratio, 4.5)
		self.assertFalse(passes_aa(fg, bg, large_text=False))
		self.assertTrue(passes_aa(fg, bg, large_text=True))


class TestMixHex(unittest.TestCase):
	def test_endpoints_are_the_inputs(self):
		self.assertEqual(mix_hex("#336699", "#ffffff", 1), "#336699")
		self.assertEqual(mix_hex("#336699", "#ffffff", 0), "#ffffff")

	def test_half_and_half(self):
		self.assertEqual(mix_hex("#000000", "#ffffff", 0.5), "#808080")

	def test_half_rounds_up_like_the_browser(self):
		# 0x01 * 0.5 = 0.5 — Math.round gives 1, Python's round() gives 0.
		self.assertEqual(mix_hex("#010101", "#000000", 0.5), "#010101")

	def test_accepts_short_and_alpha_forms(self):
		self.assertEqual(mix_hex("#fff", "#0000", 1), "#ffffff")

	def test_weight_is_clamped(self):
		self.assertEqual(mix_hex("#123456", "#000000", 7), "#123456")
		self.assertEqual(mix_hex("#123456", "#000000", -1), "#000000")


class TestPickTextColor(unittest.TestCase):
	def test_white_on_dark_black_on_light(self):
		self.assertEqual(pick_text_color(["#1e1b4b"]), "#ffffff")
		self.assertEqual(pick_text_color(["#fef3c7"]), "#000000")

	def test_preferred_wins_when_it_passes(self):
		self.assertEqual(pick_text_color(["#1e1b4b"], preferred="#e0e7ff"), "#e0e7ff")

	def test_preferred_loses_when_it_fails(self):
		# Dark theme text on a light accent: not readable, so auto takes over.
		self.assertEqual(pick_text_color(["#a5b4fc"], preferred="#e8eaf2"), "#000000")

	def test_judged_on_the_worst_background(self):
		# Light end alone would take black; the dark end rules it out.
		self.assertEqual(pick_text_color(["#3b82f6", "#1e3a8a"]), "#ffffff")
		for bg in ("#3b82f6", "#1e3a8a"):
			self.assertGreaterEqual(contrast_ratio("#ffffff", bg), 3.0)

	def test_no_background_falls_back(self):
		self.assertEqual(pick_text_color([], preferred="#111111"), "#111111")
		self.assertEqual(pick_text_color([]), "#000000")

	def test_malformed_preferred_is_ignored(self):
		self.assertEqual(pick_text_color(["#000000"], preferred="nope"), "#ffffff")


if __name__ == "__main__":
	unittest.main()
