"""Derive a complete theme palette from a single brand colour.

Why this exists
---------------
Authoring a theme by hand means setting eleven colour tokens and keeping
three WCAG invariants true across all of them. That is slow, and the usual
failure mode is a palette that looks right to the author on their monitor
and fails AA for everyone else. This module takes one seed colour — the
brand colour — and produces a full token set that passes by construction.

It complements `palettes.py` rather than replacing it: that module ships a
fixed set of hand-tuned palettes, this one generates an unlimited number
from a colour the user supplies. Both feed the editor through exactly the
same shape, so the UI renders them with the same card component.

How the derivation works
------------------------
The naive approach is to pick HSL lightness values (canvas at 98%, text at
12%, and so on). That breaks across hues, because HSL lightness is not
perceptual: a yellow at L=50% is far brighter than a blue at L=50%, so the
same recipe yields a readable palette from one seed and an unreadable one
from another.

Instead every token is defined by a *target contrast ratio against the
canvas* and solved for. Contrast is computed from WCAG relative luminance,
which is perceptually anchored, so "muted text sits at 4.8:1" means the
same thing whatever hue the brand colour is. The invariants the app already
enforces are therefore satisfied by construction rather than by luck, and
`report()` re-measures them so the caller never has to trust that claim.

Contrast is monotonic in lightness for a fixed hue and saturation, which is
what makes the binary search in `_solve_lightness` valid.

This module deliberately imports no `frappe`. It is pure input-to-output
logic and is unit-tested without a site, the same way `contrast.py`,
`css_safety.py` and `web_css.py` are.
"""

import colorsys

from nexus_theme.utils.contrast import contrast_ratio

# The eleven colour tokens a Theme Definition carries. Kept as an explicit
# tuple so a caller can assert completeness without importing the DocType.
GENERATED_FIELDS = (
	"bg_primary",
	"bg_surface",
	"bg_input",
	"text_primary",
	"text_muted",
	"accent",
	"accent_hover",
	"button_bg",
	"button_text",
	"button_hover_bg",
	"border",
)


# ---------------------------------------------------------------------------
# Colour space helpers
# ---------------------------------------------------------------------------


def _normalize_hex(value: str) -> str:
	"""Accept '#abc', 'abc', '#aabbcc' or 'aabbcc'; return '#aabbcc'."""
	h = (value or "").strip().lstrip("#").lower()
	if len(h) == 3:
		h = "".join(c * 2 for c in h)
	if len(h) != 6 or any(c not in "0123456789abcdef" for c in h):
		raise ValueError(f"invalid hex color: {value!r}")
	return "#" + h


def _hex_to_hls(hex_color: str) -> tuple[float, float, float]:
	h = _normalize_hex(hex_color).lstrip("#")
	r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
	return colorsys.rgb_to_hls(r, g, b)


def _hls_to_hex(hue: float, light: float, sat: float) -> str:
	light = min(1.0, max(0.0, light))
	sat = min(1.0, max(0.0, sat))
	r, g, b = colorsys.hls_to_rgb(hue, light, sat)
	return "#" + "".join(f"{round(c * 255):02x}" for c in (r, g, b))


def _luminance_of(hex_color: str) -> float:
	"""Relative luminance, derived through the public contrast API.

	Contrast against pure black is (L + 0.05) / 0.05, so L falls straight
	out of it. Avoids duplicating the luminance maths that contrast.py
	already owns.
	"""
	return contrast_ratio(hex_color, "#000000") * 0.05 - 0.05


def _solve_lightness(hue: float, sat: float, bg_hex: str, target: float, lighter: bool) -> str:
	"""Lightness that puts (hue, sat) at `target` contrast against `bg_hex`.

	`lighter` selects which side of the background to search. Contrast rises
	monotonically as lightness moves away from the background, so a plain
	bisection converges. When the target is unreachable at this saturation —
	a vivid yellow can never be dark — the search settles at the extreme,
	which is the closest available answer; callers that care use
	`_solve_with_desaturation` instead.
	"""
	lo, hi = 0.0, 1.0
	for _ in range(40):
		mid = (lo + hi) / 2
		ratio = contrast_ratio(_hls_to_hex(hue, mid, sat), bg_hex)
		if lighter:
			# Higher lightness -> more contrast against a darker canvas.
			if ratio < target:
				lo = mid
			else:
				hi = mid
		else:
			if ratio < target:
				hi = mid
			else:
				lo = mid
	return _hls_to_hex(hue, (lo + hi) / 2, sat)


def _solve_with_desaturation(hue: float, sat: float, bg_hex: str, target: float, lighter: bool) -> str:
	"""As `_solve_lightness`, but drop saturation until the target is met.

	Saturated hues have a bounded luminance range — pure yellow cannot get
	dark enough for 4.5:1 on white at any lightness. Bleeding saturation off
	is the standard fix and keeps the hue recognisable, which matters when
	the colour in question is someone's brand.
	"""
	best = _solve_lightness(hue, sat, bg_hex, target, lighter)
	if contrast_ratio(best, bg_hex) >= target - 0.01:
		return best
	for factor in (0.85, 0.7, 0.55, 0.4, 0.25, 0.1, 0.0):
		candidate = _solve_lightness(hue, sat * factor, bg_hex, target, lighter)
		if contrast_ratio(candidate, bg_hex) >= target - 0.01:
			return candidate
		best = candidate
	return best


def _shift_lightness(hex_color: str, delta: float) -> str:
	"""Nudge a colour lighter or darker while holding hue and saturation."""
	hue, light, sat = _hex_to_hls(hex_color)
	return _hls_to_hex(hue, light + delta, sat)


def _best_foreground(bg_hex: str, dark_ink: str, light_ink: str) -> str:
	"""Pick whichever of two inks reads better on `bg_hex`."""
	if contrast_ratio(dark_ink, bg_hex) >= contrast_ratio(light_ink, bg_hex):
		return dark_ink
	return light_ink


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------

# Each variant is a different reading of the same brand colour, not a
# different quality bar — all three clear AA. `ink_sat` is how much of the
# brand hue bleeds into text; the canvas keys set the base surface.
#
# The canvas is specified per polarity rather than shared, because HLS
# saturation behaves very differently at the two ends of the lightness
# range: at L=0.99 even S=1.0 is indistinguishable from white, so a light
# tinted canvas has to give up some lightness before any hue is visible at
# all. Dark canvases show a tint readily and need far less saturation.
VARIANTS = {
	"neutral": {
		"label": "Neutral Canvas",
		"description": "Greyscale surfaces, brand colour reserved for accents. The safest for dense screens.",
		"canvas_light": 0.995,
		"canvas_sat": 0.02,
		"dark_canvas_light": 0.055,
		"dark_canvas_sat": 0.03,
		"ink_sat": 0.05,
		"text_target": 15.5,
		"muted_target": 4.8,
		"border_ratio": 1.5,
	},
	"tinted": {
		"label": "Tinted Canvas",
		"description": "Surfaces carry a whisper of the brand hue. Warmer, more branded.",
		"canvas_light": 0.968,
		"canvas_sat": 0.55,
		"dark_canvas_light": 0.072,
		"dark_canvas_sat": 0.22,
		"ink_sat": 0.10,
		"text_target": 15.0,
		"muted_target": 4.8,
		"border_ratio": 1.6,
	},
	"contrast": {
		"label": "High Contrast",
		"description": "AAA-level text and stronger borders. Built for accessibility and bright rooms.",
		"canvas_light": 1.0,
		"canvas_sat": 0.0,
		"dark_canvas_light": 0.04,
		"dark_canvas_sat": 0.0,
		"ink_sat": 0.0,
		"text_target": 17.5,
		"muted_target": 7.2,
		"border_ratio": 3.0,
	},
}

VARIANT_ORDER = ("neutral", "tinted", "contrast")


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def generate(seed: str, is_dark: bool = False, variant: str = "neutral") -> dict:
	"""Return the eleven colour tokens derived from `seed`.

	`seed` is the brand colour. `is_dark` selects the polarity, `variant` one
	of VARIANTS. Raises ValueError on an unparseable seed or unknown variant.
	"""
	if variant not in VARIANTS:
		raise ValueError(f"unknown variant: {variant!r}")
	spec = VARIANTS[variant]

	hue, _seed_light, seed_sat = _hex_to_hls(seed)
	# A greyscale seed has an arbitrary hue; clamping saturation to a floor
	# would invent a colour the user did not choose, so accents stay grey.
	chromatic = 1.0 if seed_sat > 0.05 else 0.0
	accent_sat = seed_sat
	ink_sat = spec["ink_sat"] * chromatic
	canvas_light = spec["dark_canvas_light"] if is_dark else spec["canvas_light"]
	canvas_sat = (spec["dark_canvas_sat"] if is_dark else spec["canvas_sat"]) * chromatic

	if is_dark:
		bg_primary = _hls_to_hex(hue, canvas_light, canvas_sat)
		# Dark UIs separate by elevation: surfaces sit *above* the canvas.
		bg_surface = _solve_lightness(hue, canvas_sat, bg_primary, 1.14, lighter=True)
		bg_input = _solve_lightness(hue, canvas_sat, bg_primary, 1.24, lighter=True)
		border = _solve_lightness(hue, canvas_sat, bg_primary, spec["border_ratio"] + 0.2, lighter=True)
		text_primary = _solve_with_desaturation(
			hue, ink_sat, bg_primary, min(spec["text_target"], 14.5), lighter=True
		)
		text_muted = _solve_with_desaturation(hue, ink_sat, bg_primary, spec["muted_target"], lighter=True)
		accent = _solve_with_desaturation(hue, accent_sat, bg_primary, 5.0, lighter=True)
		accent_hover = _shift_lightness(accent, 0.08)
		# The button is a filled block, so it wants a mid-tone that still
		# leaves room for its own label to clear AA.
		button_bg = _solve_with_desaturation(hue, accent_sat, bg_primary, 3.4, lighter=True)
		button_hover_bg = _shift_lightness(button_bg, 0.06)
	else:
		bg_primary = _hls_to_hex(hue, canvas_light, canvas_sat)
		bg_surface = _solve_lightness(hue, canvas_sat, bg_primary, 1.05, lighter=False)
		# Inputs read as wells the user can type into, so they stay the
		# lightest surface on the page rather than matching a tinted canvas.
		bg_input = _hls_to_hex(hue, min(1.0, canvas_light + 0.03), canvas_sat * 0.35)
		border = _solve_lightness(hue, canvas_sat, bg_primary, spec["border_ratio"], lighter=False)
		text_primary = _solve_with_desaturation(hue, ink_sat, bg_primary, spec["text_target"], lighter=False)
		text_muted = _solve_with_desaturation(hue, ink_sat, bg_primary, spec["muted_target"], lighter=False)
		accent = _solve_with_desaturation(hue, accent_sat, bg_primary, 4.8, lighter=False)
		accent_hover = _shift_lightness(accent, -0.07)
		button_bg = accent
		button_hover_bg = _shift_lightness(accent, -0.07)

	colors = {
		"bg_primary": bg_primary,
		"bg_surface": bg_surface,
		"bg_input": bg_input,
		"text_primary": text_primary,
		"text_muted": text_muted,
		"accent": accent,
		"accent_hover": accent_hover,
		"button_bg": button_bg,
		"button_text": _best_foreground(button_bg, "#111111", "#ffffff"),
		"button_hover_bg": button_hover_bg,
		"border": border,
	}
	return _enforce(colors)


def _enforce(colors: dict) -> dict:
	"""Last-resort repair of the three invariants Theme Definition validates.

	The targeted derivation above should already satisfy all of them; this
	exists so that an unreachable target — an extreme seed, or a future edit
	to the variant table — degrades to a passing palette instead of a
	rejected one. `theme_definition.py` *throws* on a failing default theme,
	so silently emitting one would surface as a failed save, far from the
	cause.
	"""
	text_bg = contrast_ratio(colors["text_primary"], colors["bg_primary"])
	text_surface = contrast_ratio(colors["text_primary"], colors["bg_surface"])
	if min(text_bg, text_surface) < 4.5:
		# Push the ink to whichever pole the canvas is not.
		worst_bg = colors["bg_primary"] if text_bg <= text_surface else colors["bg_surface"]
		hue, _l, sat = _hex_to_hls(colors["text_primary"])
		lighter = _luminance_of(worst_bg) < 0.5
		colors["text_primary"] = _solve_with_desaturation(hue, sat, worst_bg, 4.6, lighter=lighter)

	if contrast_ratio(colors["text_muted"], colors["bg_surface"]) < 4.5:
		hue, _l, sat = _hex_to_hls(colors["text_muted"])
		lighter = _luminance_of(colors["bg_surface"]) < 0.5
		colors["text_muted"] = _solve_with_desaturation(hue, sat, colors["bg_surface"], 4.6, lighter=lighter)

	if contrast_ratio(colors["button_text"], colors["button_bg"]) < 4.5:
		colors["button_text"] = _best_foreground(colors["button_bg"], "#000000", "#ffffff")
	return colors


def report(colors: dict) -> dict:
	"""Measured contrast for the pairs the app validates, for display in the UI."""
	pairs = {
		"text_on_background": ("text_primary", "bg_primary", 4.5),
		"text_on_surface": ("text_primary", "bg_surface", 4.5),
		"muted_on_surface": ("text_muted", "bg_surface", 4.5),
		"accent_on_background": ("accent", "bg_primary", 4.5),
		"button_text_on_button": ("button_text", "button_bg", 3.0),
	}
	out = {}
	for key, (fg, bg, target) in pairs.items():
		ratio = contrast_ratio(colors[fg], colors[bg])
		out[key] = {
			"ratio": round(ratio, 2),
			"target": target,
			"passes": ratio >= target,
		}
	return out


def generate_variants(seed: str, is_dark: bool = False) -> list[dict]:
	"""Every variant for one seed, shaped like `palettes.get_palettes()`.

	Matching that shape is deliberate: the editor renders generated palettes
	with the same card component as the curated ones, so there is a single
	place where a palette is drawn.

	A variant that somehow fails its own contrast report is dropped rather
	than offered, mirroring `get_palettes()`.
	"""
	seed = _normalize_hex(seed)
	out = []
	for key in VARIANT_ORDER:
		spec = VARIANTS[key]
		try:
			colors = generate(seed, is_dark=is_dark, variant=key)
		except ValueError:
			continue
		checks = report(colors)
		if not all(c["passes"] for c in checks.values()):
			continue
		out.append(
			{
				"key": f"generated-{key}",
				"label": spec["label"],
				"description": spec["description"],
				"category": "Dark" if is_dark else "Light",
				"is_dark": 1 if is_dark else 0,
				"seed": seed,
				"colors": colors,
				"contrast": checks,
			}
		)
	return out
