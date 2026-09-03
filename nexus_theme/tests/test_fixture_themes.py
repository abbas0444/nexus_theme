"""Validation for the Theme Definition fixtures shipped with the app.

Pure-logic tests — no database or Frappe site required.

These matter because the shipped themes carry `is_default: 1`, and
ThemeDefinition._validate_contrast() *throws* (rather than warning) for
default themes. A fixture whose contrast slips below AA therefore does not
degrade quietly — it aborts `bench migrate` when patch v1_0 inserts it. The
same goes for css_safety: a value the guard rejects blocks the insert.

Catching that here keeps a palette edit from breaking installs.
"""

import json
import unittest
from pathlib import Path

from nexus_theme.utils.contrast import contrast_ratio
from nexus_theme.utils.css_safety import (
	COLOR_FIELDS,
	STYLE_FIELDS,
	is_safe_value,
)

FIXTURE = (
	Path(__file__).resolve().parent.parent / "fixtures" / "theme_definition.json"
)

# Fonts Frappe actually ships, plus stacks the OS is guaranteed to resolve.
# Naming anything else (e.g. "JetBrains Mono") silently falls back to a
# generic family, which is how themes end up not looking like their preview.
BUNDLED_FIRST_CHOICES = {"InterVariable", "ui-monospace", "Georgia"}


def load_themes():
	with open(FIXTURE) as f:
		return json.load(f)


class TestFixtureThemes(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.themes = load_themes()

	def test_fixture_is_not_empty(self):
		self.assertGreater(len(self.themes), 0)

	def test_theme_keys_are_unique(self):
		keys = [t["theme_key"] for t in self.themes]
		self.assertEqual(len(keys), len(set(keys)), "duplicate theme_key in fixtures")

	def test_name_matches_theme_key(self):
		# Theme Definition is autonamed `field:theme_key`, so a fixture whose
		# `name` disagrees would insert under one id and be looked up by another.
		for t in self.themes:
			self.assertEqual(t["name"], t["theme_key"], t["theme_name"])

	def test_every_value_passes_css_safety(self):
		for t in self.themes:
			for field in (*COLOR_FIELDS, *STYLE_FIELDS):
				if field not in t:
					continue
				self.assertTrue(
					is_safe_value(field, t[field]),
					f"{t['theme_name']}: {field}={t[field]!r} rejected by css_safety",
				)

	def test_enforced_contrast_pairs_pass(self):
		"""The three pairs theme_definition.py throws on for default themes."""
		pairs = [
			("text_primary", "bg_primary", 4.5),
			("text_primary", "bg_surface", 4.5),
			("button_text", "button_bg", 3.0),
		]
		for t in self.themes:
			for fg, bg, target in pairs:
				ratio = contrast_ratio(t[fg], t[bg])
				self.assertGreaterEqual(
					ratio,
					target,
					f"{t['theme_name']}: {fg} on {bg} is {ratio:.2f}, needs {target}",
				)

	def test_muted_text_is_readable(self):
		"""Not enforced by the app, but muted text is still body text."""
		for t in self.themes:
			for bg in ("bg_primary", "bg_surface"):
				ratio = contrast_ratio(t["text_muted"], t[bg])
				self.assertGreaterEqual(
					ratio,
					4.5,
					f"{t['theme_name']}: text_muted on {bg} is {ratio:.2f}",
				)

	def test_accent_meets_non_text_contrast(self):
		"""WCAG 1.4.11: UI components and graphics need 3:1."""
		for t in self.themes:
			ratio = contrast_ratio(t["accent"], t["bg_primary"])
			self.assertGreaterEqual(
				ratio, 3.0, f"{t['theme_name']}: accent is {ratio:.2f}"
			)

	def test_font_stacks_start_with_a_resolvable_family(self):
		for t in self.themes:
			first = t["font_family"].split(",")[0].strip().strip('"').strip("'")
			self.assertIn(
				first,
				BUNDLED_FIRST_CHOICES,
				f"{t['theme_name']}: font stack leads with {first!r}, which Frappe "
				f"does not bundle — it would fall back to a generic family",
			)

	def test_dark_flag_matches_the_palette(self):
		# A theme claiming is_dark must actually have a dark canvas, otherwise
		# the switcher groups and previews it wrongly.
		white = "#ffffff"
		for t in self.themes:
			light_bg = contrast_ratio(t["bg_primary"], white) < 2.0
			self.assertEqual(
				bool(t["is_dark"]),
				not light_bg,
				f"{t['theme_name']}: is_dark={t['is_dark']} contradicts bg_primary",
			)

	def test_all_shipped_themes_are_defaults(self):
		# hooks.py exports fixtures filtered on is_default == 1; a theme
		# without the flag would ship in the file but never be re-exported.
		for t in self.themes:
			self.assertEqual(t["is_default"], 1, t["theme_name"])


if __name__ == "__main__":
	unittest.main()
