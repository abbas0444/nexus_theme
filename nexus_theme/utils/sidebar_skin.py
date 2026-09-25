"""The sidebar skin: which colours a theme's sidebar actually paints.

A Theme Definition only stores what the author chose. `sidebar_bg`,
`sidebar_text` and `sidebar_active_bg` are all optional, and an empty one
means "derive it": the accent for a Solid or Gradient sidebar, a light
accent tint for a Tinted one, and a text colour picked for contrast. The
WCAG check has to judge the derived colours, not the empty fields, so the
derivation lives here — free of any `frappe` import, like contrast.py —
and theme_manager.js (NexusSidebarSkin.resolve) mirrors it step for step.
"""

from nexus_theme.utils.contrast import contrast_ratio, mix_hex, pick_text_color

SIDEBAR_STYLES = ("Plain", "Tinted", "Solid", "Gradient")

# How much accent a Tinted sidebar carries over the theme's surface colour.
TINT_WEIGHT = 0.14
# A Gradient runs from the sidebar colour to this much of it over black.
GRADIENT_END_WEIGHT = 0.72
# The active item on a Solid/Gradient sidebar is the text colour washed
# over the sidebar. The first weight that keeps the text readable wins; when
# none does (a sidebar only just past AA), the item is shaded the other way
# instead — away from the text — which can only add contrast.
ACTIVE_WEIGHTS = (0.18, 0.14, 0.1)
ACTIVE_SHADE_WEIGHT = 0.8

_FALLBACK_ACCENT = "#4f46e5"


def normalize_style(value) -> str:
	"""The style a stored value means. Anything unknown is Plain."""
	return value if value in SIDEBAR_STYLES else "Plain"


def _is_hex(value) -> bool:
	if not isinstance(value, str):
		return False
	try:
		contrast_ratio(value, "#000000")
	except ValueError:
		return False
	return True


def _pick(values: dict, field: str, fallback=None):
	value = values.get(field)
	if value in (None, "") or not _is_hex(value):
		return fallback
	return value


def resolve_sidebar(values: dict) -> dict | None:
	"""The effective sidebar colours for a theme, or None for Plain.

	Returns `style`, `bg`, `bg_end` (the same as `bg` unless Gradient),
	`text` and `active_bg`, every one a hex colour.
	"""
	values = values or {}
	style = normalize_style(values.get("sidebar_style"))
	if style == "Plain":
		return None

	accent = _pick(values, "accent", _FALLBACK_ACCENT)
	surface = _pick(values, "bg_surface") or _pick(values, "bg_primary", "#ffffff")
	page = _pick(values, "bg_primary", surface)

	bg = _pick(values, "sidebar_bg")
	if not bg:
		bg = mix_hex(accent, surface, TINT_WEIGHT) if style == "Tinted" else accent
	bg_end = mix_hex(bg, "#000000", GRADIENT_END_WEIGHT) if style == "Gradient" else bg

	text = _pick(values, "sidebar_text")
	if not text:
		text = pick_text_color([bg, bg_end], preferred=_pick(values, "text_primary"))

	active = _pick(values, "sidebar_active_bg")
	if not active:
		if style == "Tinted":
			# The raised pill of the stock sidebar: the page colour.
			active = page
		else:
			active = None
			for weight in ACTIVE_WEIGHTS:
				candidate = mix_hex(text, bg, weight)
				if contrast_ratio(text, candidate) >= 4.5:
					active = candidate
					break
			if active is None:
				light_text = contrast_ratio(text, "#000000") >= contrast_ratio(text, "#ffffff")
				away = "#000000" if light_text else "#ffffff"
				active = mix_hex(bg, away, ACTIVE_SHADE_WEIGHT)

	return {"style": style, "bg": bg, "bg_end": bg_end, "text": text, "active_bg": active}


def sidebar_contrast_failures(values: dict) -> list[tuple[str, float]]:
	"""Every (surface, ratio) where the sidebar text misses AA (4.5:1).

	Empty for Plain, and for a sidebar that reads everywhere. The surfaces
	are the sidebar itself, the far end of a gradient and the active item.
	"""
	skin = resolve_sidebar(values)
	if not skin:
		return []
	surfaces = [("sidebar_bg", skin["bg"])]
	if skin["bg_end"] != skin["bg"]:
		surfaces.append(("sidebar_bg (gradient end)", skin["bg_end"]))
	surfaces.append(("sidebar_active_bg", skin["active_bg"]))
	failures = []
	for label, surface in surfaces:
		ratio = contrast_ratio(skin["text"], surface)
		if ratio < 4.5:
			failures.append((label, ratio))
	return failures
