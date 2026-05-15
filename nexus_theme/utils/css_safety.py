"""Validation for theme style values that get injected into the DOM as CSS.

Theme color/style fields flow into `style="…"` attributes and CSS custom
properties on every user's Desk. A Theme Definition can be shared publicly
(`is_public`), so any other user who opens Theme Studio renders the shared
values — an unvalidated string here is a stored, cross-user CSS-injection
vector (tracking beacons via `url(...)`, UI defacement). Every value that
reaches the DOM must match one of these strict patterns.

This module is intentionally free of any `frappe` import so it stays pure
and unit-testable; callers do the throwing / sanitizing.
"""

import re

# #rgb, #rgba, #rrggbb, #rrggbbaa — the only color forms we accept.
_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

# CSS font-family stacks: letters, digits, spaces, commas, quotes, hyphens.
# Deliberately excludes ; ( ) { } : / * < > which enable declaration breakout.
_FONT_FAMILY_RE = re.compile(r"^[A-Za-z0-9 ,\"'-]+$")

_SIZE_RE = re.compile(r"^\d+(?:\.\d+)?(?:px|rem|em|pt)$")
_DURATION_RE = re.compile(r"^\d+(?:\.\d+)?m?s$")
_RADIUS_RE = re.compile(r"^\d+(?:\.\d+)?(?:px|rem|em|%)$")
_WEIGHT_RE = re.compile(r"^[1-9]\d{0,2}$")

# Theme Definition fields that must hold a hex color.
COLOR_FIELDS = (
	"bg_primary",
	"bg_surface",
	"bg_input",
	"text_primary",
	"text_muted",
	"border",
	"accent",
	"accent_hover",
	"button_bg",
	"button_text",
	"button_hover_bg",
)

# Non-color style fields → the pattern their value must match.
_STYLE_VALIDATORS = {
	"font_family": _FONT_FAMILY_RE,
	"font_size_base": _SIZE_RE,
	"transition_duration": _DURATION_RE,
	"border_radius": _RADIUS_RE,
	"font_weight_base": _WEIGHT_RE,
}

# Public tuple of the non-color style fields, for callers that want to iterate.
STYLE_FIELDS = tuple(_STYLE_VALIDATORS)


def is_safe_value(field: str, value) -> bool:
	"""True if `value` is safe to inject as CSS for `field`.

	An empty value is always safe (the client falls back to a default).
	An unknown field name is treated as unsafe so new fields can't slip
	through unvalidated."""
	if value in (None, ""):
		return True
	value = str(value).strip()
	if field in COLOR_FIELDS:
		return bool(_HEX_RE.match(value))
	validator = _STYLE_VALIDATORS.get(field)
	if validator is not None:
		return bool(validator.match(value))
	return False


def sanitize_overrides(overrides: dict) -> dict:
	"""Return a copy of `overrides` with every unsafe entry dropped.

	Used for the per-user `overrides_json` blob. Unlike a shared Theme
	Definition (where we reject the whole save), here we silently discard
	only the offending keys — a stale or hand-edited override should not
	block the user from saving the rest of their preference."""
	if not isinstance(overrides, dict):
		return {}
	clean = {}
	for key, val in overrides.items():
		if (key in COLOR_FIELDS or key in _STYLE_VALIDATORS) and is_safe_value(key, val):
			clean[key] = val
		elif key == "enable_hover_lift":
			# Coerced to "1"/"0" before it touches the DOM — safe as-is.
			clean[key] = 1 if val else 0
	return clean
