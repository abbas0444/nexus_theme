"""Unit tests for the WCAG contrast helpers.

Pure-logic tests — no database or Frappe site required.
"""

import unittest

from nexus_theme.utils.contrast import (
	_normalize_hex,
	contrast_ratio,
	passes_aa,
)


class TestContrast(unittest.TestCase):
	def test_normalize_expands_three_digit_hex(self):
		self.assertEqual(_normalize_hex("#fff"), "ffffff")
		self.assertEqual(_normalize_hex("000"), "000000")

	def test_normalize_strips_hash_and_whitespace(self):
		self.assertEqual(_normalize_hex("  #1E293B  "), "1E293B")

	def test_normalize_rejects_wrong_length_hex(self):
		for bad in ("", "#12", "12345", "#1234567"):
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


if __name__ == "__main__":
	unittest.main()
