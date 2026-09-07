"""Validation for the single-colour palette generator.

Pure-logic tests — no database or Frappe site required.

These matter for the same reason test_fixture_themes.py does. Anything the
generator emits can be saved as a Theme Definition, and that DocType
*throws* on a palette failing its contrast pairs or its CSS-safety guard.
A seed hue that produced a marginal palette would therefore not degrade
quietly; it would surface as a failed save with the cause several steps
away from the symptom.

The hue sweep is the important test here. The generator's whole reason for
targeting contrast ratios rather than HSL lightness values is that the
latter breaks across hues, so the suite checks every hue rather than the
handful a developer would think to try by hand.
"""

import colorsys
import re
import unittest

from nexus_theme.utils.contrast import contrast_ratio
from nexus_theme.utils.css_safety import is_safe_value
from nexus_theme.utils.palette_generator import (
	GENERATED_FIELDS,
	VARIANT_ORDER,
	_normalize_hex,
	generate,
	generate_variants,
	report,
)

HEX_RE = re.compile(r"^#[0-9a-f]{6}$")


def _hue_sweep(step: int = 10, light: float = 0.5, sat: float = 0.85) -> list[str]:
	"""Fully saturated seeds all the way round the colour wheel."""
	out = []
	for deg in range(0, 360, step):
		r, g, b = colorsys.hls_to_rgb(deg / 360, light, sat)
		out.append("#" + "".join(f"{round(c * 255):02x}" for c in (r, g, b)))
	return out


# Seeds chosen to break things: the achromatic poles, a fully saturated
# yellow (the classic case where no lightness reaches 4.5:1 on white), and
# near-black / near-white values that sit at the edge of the search range.
EDGE_SEEDS = [
	"#000000",
	"#ffffff",
	"#808080",
	"#ffff00",
	"#00ff00",
	"#0000ff",
	"#010101",
	"#fefefe",
	"#8c6f3f",
]

ALL_SEEDS = _hue_sweep() + EDGE_SEEDS


class TestHexParsing(unittest.TestCase):
	def test_accepts_the_usual_spellings(self):
		for value in ("#abc", "abc", "#AABBCC", "aabbcc", "  #AaBbCc  "):
			self.assertTrue(HEX_RE.match(_normalize_hex(value)), value)

	def test_shorthand_expands(self):
		self.assertEqual(_normalize_hex("#abc"), "#aabbcc")

	def test_rejects_garbage(self):
		for value in ("", None, "#12", "#12345", "nope", "#gggggg", "rgb(1,2,3)"):
			with self.assertRaises(ValueError, msg=repr(value)):
				_normalize_hex(value)


class TestGeneratedShape(unittest.TestCase):
	def test_every_token_present_and_well_formed(self):
		for seed in ALL_SEEDS:
			for is_dark in (False, True):
				for variant in VARIANT_ORDER:
					colors = generate(seed, is_dark=is_dark, variant=variant)
					self.assertEqual(set(colors), set(GENERATED_FIELDS))
					for field, value in colors.items():
						self.assertTrue(
							HEX_RE.match(value),
							f"{seed} {variant} {field} = {value!r}",
						)

	def test_unknown_variant_rejected(self):
		with self.assertRaises(ValueError):
			generate("#4f46e5", variant="does-not-exist")

	def test_is_deterministic(self):
		first = generate("#4f46e5", is_dark=True, variant="tinted")
		second = generate("#4f46e5", is_dark=True, variant="tinted")
		self.assertEqual(first, second)


class TestContrastInvariants(unittest.TestCase):
	"""The three pairs ThemeDefinition._validate_contrast() enforces."""

	def test_invariants_hold_for_every_seed(self):
		failures = []
		for seed in ALL_SEEDS:
			for is_dark in (False, True):
				for variant in VARIANT_ORDER:
					c = generate(seed, is_dark=is_dark, variant=variant)
					label = f"{seed}/{variant}/{'dark' if is_dark else 'light'}"
					checks = (
						("text on bg", c["text_primary"], c["bg_primary"], 4.5),
						("text on surface", c["text_primary"], c["bg_surface"], 4.5),
						("button text", c["button_text"], c["button_bg"], 3.0),
					)
					for name, fg, bg, target in checks:
						ratio = contrast_ratio(fg, bg)
						if ratio < target:
							failures.append(f"{label}: {name} {ratio:.2f} < {target}")
		self.assertEqual(failures, [], "\n".join(failures[:20]))

	def test_muted_text_is_readable_on_surface(self):
		"""Not enforced by the DocType, but muted text is still body text."""
		failures = []
		for seed in ALL_SEEDS:
			for is_dark in (False, True):
				c = generate(seed, is_dark=is_dark)
				ratio = contrast_ratio(c["text_muted"], c["bg_surface"])
				if ratio < 4.5:
					failures.append(f"{seed}: muted {ratio:.2f}")
		self.assertEqual(failures, [])

	def test_accent_is_readable_as_a_link(self):
		failures = []
		for seed in ALL_SEEDS:
			for is_dark in (False, True):
				c = generate(seed, is_dark=is_dark)
				ratio = contrast_ratio(c["accent"], c["bg_primary"])
				if ratio < 4.5:
					failures.append(f"{seed}: accent {ratio:.2f}")
		self.assertEqual(failures, [])


class TestCssSafety(unittest.TestCase):
	def test_every_value_is_safe_to_inject(self):
		"""Generated colours are written into a live Desk as CSS."""
		for seed in ALL_SEEDS:
			for is_dark in (False, True):
				for field, value in generate(seed, is_dark=is_dark).items():
					self.assertTrue(is_safe_value(field, value), f"{field}={value!r}")


class TestDesignRules(unittest.TestCase):
	"""The conventions palettes.py documents for the hand-tuned palettes."""

	def _lum(self, hex_color: str) -> float:
		return contrast_ratio(hex_color, "#000000") * 0.05 - 0.05

	def test_dark_surfaces_sit_above_the_canvas(self):
		for seed in ALL_SEEDS:
			c = generate(seed, is_dark=True)
			self.assertGreater(self._lum(c["bg_surface"]), self._lum(c["bg_primary"]), seed)

	def test_light_surfaces_sit_below_the_canvas(self):
		for seed in ALL_SEEDS:
			c = generate(seed, is_dark=False)
			self.assertLess(self._lum(c["bg_surface"]), self._lum(c["bg_primary"]), seed)

	def test_greyscale_seed_produces_greyscale_canvas(self):
		"""A grey brand colour must not have a hue invented for it."""
		for seed in ("#808080", "#000000", "#ffffff"):
			for is_dark in (False, True):
				c = generate(seed, is_dark=is_dark, variant="tinted")
				h = c["bg_primary"].lstrip("#")
				r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
				self.assertEqual({r}, {r, g, b}, f"{seed} -> {c['bg_primary']}")

	def test_variants_are_actually_different(self):
		"""Three identical cards would be a worse UI than one."""
		for is_dark in (False, True):
			canvases = {generate("#4f46e5", is_dark=is_dark, variant=v)["bg_primary"] for v in VARIANT_ORDER}
			self.assertEqual(len(canvases), len(VARIANT_ORDER), canvases)


class TestVariantEnvelope(unittest.TestCase):
	def test_shape_matches_the_curated_palette_contract(self):
		"""The editor draws generated and curated palettes with one card."""
		variants = generate_variants("#8c6f3f", is_dark=False)
		self.assertEqual(len(variants), len(VARIANT_ORDER))
		for v in variants:
			self.assertEqual(
				{"key", "label", "description", "category", "is_dark", "seed", "colors", "contrast"},
				set(v),
			)
			self.assertIn(v["is_dark"], (0, 1))
			self.assertEqual(set(v["colors"]), set(GENERATED_FIELDS))

	def test_polarity_is_carried_on_the_envelope(self):
		"""Applying a dark palette has to flip <html> polarity too."""
		for is_dark in (False, True):
			for v in generate_variants("#0ea5e9", is_dark=is_dark):
				self.assertEqual(v["is_dark"], 1 if is_dark else 0)
				self.assertEqual(v["category"], "Dark" if is_dark else "Light")

	def test_no_variant_is_dropped_across_the_wheel(self):
		"""A dropped variant means the derivation could not reach AA."""
		for seed in ALL_SEEDS:
			for is_dark in (False, True):
				self.assertEqual(
					len(generate_variants(seed, is_dark)),
					len(VARIANT_ORDER),
					f"{seed} {'dark' if is_dark else 'light'}",
				)

	def test_bad_seed_raises(self):
		with self.assertRaises(ValueError):
			generate_variants("not-a-color")

	def test_report_agrees_with_the_colors(self):
		colors = generate("#be123c", is_dark=True)
		checks = report(colors)
		self.assertTrue(all(c["passes"] for c in checks.values()), checks)
		self.assertAlmostEqual(
			checks["text_on_background"]["ratio"],
			round(contrast_ratio(colors["text_primary"], colors["bg_primary"]), 2),
			places=2,
		)


if __name__ == "__main__":
	unittest.main()
