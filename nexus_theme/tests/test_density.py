"""Unit tests for the density modes and their resolution order.

Pure-logic tests — no database or Frappe site required.
"""

import unittest

from nexus_theme.utils.density import (
	DEFAULT_DENSITY,
	MODES,
	label_for,
	normalize_density,
	resolve_density,
)


class TestDensityModes(unittest.TestCase):
	def test_there_are_three_modes_and_comfortable_is_the_default(self):
		self.assertEqual([m["key"] for m in MODES], ["compact", "comfortable", "spacious"])
		self.assertEqual(DEFAULT_DENSITY, "comfortable")
		for m in MODES:
			self.assertEqual(m["label"].lower(), m["key"])
			self.assertTrue(m["description"])

	def test_keys_and_labels_both_normalise_to_the_key(self):
		for given, want in (
			("compact", "compact"),
			("Compact", "compact"),
			("COMPACT", "compact"),
			("  spacious ", "spacious"),
			("Comfortable", "comfortable"),
		):
			self.assertEqual(normalize_density(given), want, given)

	def test_anything_else_is_not_a_mode(self):
		for bad in (None, "", "   ", "cosy", "dense", "compact;", 0, 1, "Automatic"):
			self.assertIsNone(normalize_density(bad), repr(bad))

	def test_label_for_round_trips(self):
		for m in MODES:
			self.assertEqual(label_for(m["key"]), m["label"])
			self.assertEqual(normalize_density(label_for(m["key"])), m["key"])
		self.assertRaises(KeyError, label_for, "cosy")


class TestResolveDensity(unittest.TestCase):
	def test_the_user_wins(self):
		self.assertEqual(resolve_density("Compact", "Spacious"), ("compact", "user"))

	def test_the_site_default_answers_for_a_user_without_one(self):
		self.assertEqual(resolve_density(None, "Spacious"), ("spacious", "site_default"))
		self.assertEqual(resolve_density("", "spacious"), ("spacious", "site_default"))

	def test_comfortable_when_nobody_chose(self):
		self.assertEqual(resolve_density(None, None), ("comfortable", "default"))
		self.assertEqual(resolve_density("", ""), ("comfortable", "default"))

	def test_a_value_that_names_no_mode_is_treated_as_absent(self):
		# A stale or mistyped value must fall through, not break the boot.
		self.assertEqual(resolve_density("dense", "Spacious"), ("spacious", "site_default"))
		self.assertEqual(resolve_density("dense", "roomy"), ("comfortable", "default"))
