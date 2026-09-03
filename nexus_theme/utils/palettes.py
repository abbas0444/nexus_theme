"""Curated theme palettes for the Theme Studio "Recommended" panel.

Each palette is a complete, WCAG-AA-validated set of the 11 color tokens
that Theme Definition uses, plus a key, label, and dark flag. The frontend
applies a palette by previewing it through ThemeManager.previewOverrides()
exactly the way the editor's color pickers do — no schema changes needed.

Design rules these follow, matching the shipped Theme Definitions:
  * The canvas stays neutral. Saturation belongs to the accent, not to
    every surface — a tinted background is what makes a UI read as a toy.
  * bg_surface is a small step off bg_primary, so cards and the sidebar
    separate by elevation rather than by hue.
  * text_muted is desaturated and still clears AA. It is secondary text,
    not decorative.

To add or modify a palette, keep these invariants:
  * text_primary on bg_primary  passes AA (>= 4.5:1)
  * text_primary on bg_surface  passes AA (>= 4.5:1)
  * button_text  on button_bg   passes AA-large (>= 3.0:1)

The validate_palettes() function below enforces these on import in dev.
"""

from nexus_theme.utils.contrast import passes_aa


PALETTES = [
	# ---------- LIGHT ----------
	{
		"key": "indigo-mist",
		"label": "Indigo Mist",
		"category": "Light",
		"is_dark": 0,
		"description": "Neutral whites with a deep indigo accent. Reads as classic enterprise.",
		"colors": {
			"bg_primary": "#ffffff",
			"bg_surface": "#f7f8fa",
			"bg_input": "#ffffff",
			"text_primary": "#101828",
			"text_muted": "#5a6274",
			"accent": "#4f46e5",
			"accent_hover": "#4338ca",
			"button_bg": "#4f46e5",
			"button_text": "#ffffff",
			"button_hover_bg": "#4338ca",
			"border": "#e4e7ec",
		},
	},
	{
		"key": "forest-paper",
		"label": "Forest Paper",
		"category": "Light",
		"is_dark": 0,
		"description": "Warm off-white paper, deep evergreen accent. Easy on long reads.",
		"colors": {
			"bg_primary": "#fdfcfa",
			"bg_surface": "#f6f4ef",
			"bg_input": "#ffffff",
			"text_primary": "#1f2a20",
			"text_muted": "#54614f",
			"accent": "#15803d",
			"accent_hover": "#166534",
			"button_bg": "#15803d",
			"button_text": "#ffffff",
			"button_hover_bg": "#166534",
			"border": "#e5e2d8",
		},
	},
	{
		"key": "rose-quartz",
		"label": "Rose Quartz",
		"category": "Light",
		"is_dark": 0,
		"description": "White canvas with a crimson accent. Warm without being sugary.",
		"colors": {
			"bg_primary": "#ffffff",
			"bg_surface": "#fdf5f6",
			"bg_input": "#ffffff",
			"text_primary": "#33191e",
			"text_muted": "#6f4a51",
			"accent": "#be123c",
			"accent_hover": "#9f1239",
			"button_bg": "#be123c",
			"button_text": "#ffffff",
			"button_hover_bg": "#9f1239",
			"border": "#f2dde0",
		},
	},
	{
		"key": "graphite-amber",
		"label": "Graphite Amber",
		"category": "Light",
		"is_dark": 0,
		"description": "Neutral grays with amber CTAs. High contrast, all-business.",
		"colors": {
			"bg_primary": "#ffffff",
			"bg_surface": "#f5f5f5",
			"bg_input": "#ffffff",
			"text_primary": "#18181b",
			"text_muted": "#52525b",
			"accent": "#b45309",
			"accent_hover": "#92400e",
			"button_bg": "#b45309",
			"button_text": "#ffffff",
			"button_hover_bg": "#92400e",
			"border": "#e4e4e7",
		},
	},
	# ---------- DARK ----------
	{
		"key": "midnight-violet",
		"label": "Midnight Violet",
		"category": "Dark",
		"is_dark": 1,
		"description": "Deep navy surfaces with violet accents. Premium, low-glare.",
		"colors": {
			"bg_primary": "#0f1120",
			"bg_surface": "#171a2e",
			"bg_input": "#1d2138",
			"text_primary": "#e8eaf5",
			"text_muted": "#a3aac4",
			"accent": "#a78bfa",
			"accent_hover": "#c4b5fd",
			"button_bg": "#7c3aed",
			"button_text": "#ffffff",
			"button_hover_bg": "#6d28d9",
			"border": "#2a2f4d",
		},
	},
	{
		"key": "carbon-teal",
		"label": "Carbon Teal",
		"category": "Dark",
		"is_dark": 1,
		"description": "Soft black with teal highlights. Calm, precise, developer-friendly.",
		"colors": {
			"bg_primary": "#0f1419",
			"bg_surface": "#171d23",
			"bg_input": "#1d242b",
			"text_primary": "#e6edf3",
			"text_muted": "#9ba7b4",
			"accent": "#2dd4bf",
			"accent_hover": "#5eead4",
			"button_bg": "#0f766e",
			"button_text": "#ffffff",
			"button_hover_bg": "#115e59",
			"border": "#262e36",
		},
	},
	{
		"key": "obsidian-rose",
		"label": "Obsidian Rose",
		"category": "Dark",
		"is_dark": 1,
		"description": "Near-black with rose accents. Bold, modern, attention-grabbing.",
		"colors": {
			"bg_primary": "#0b0b0d",
			"bg_surface": "#141417",
			"bg_input": "#1a1a1e",
			"text_primary": "#f4f4f6",
			"text_muted": "#a1a1aa",
			"accent": "#f472b6",
			"accent_hover": "#f9a8d4",
			"button_bg": "#db2777",
			"button_text": "#ffffff",
			"button_hover_bg": "#be185d",
			"border": "#26262b",
		},
	},
	{
		"key": "nordic-frost",
		"label": "Nordic Frost",
		"category": "Dark",
		"is_dark": 1,
		"description": "The official Nord palette — cool slate with icy blue accents.",
		"colors": {
			"bg_primary": "#2e3440",
			"bg_surface": "#3b4252",
			"bg_input": "#434c5e",
			"text_primary": "#eceff4",
			"text_muted": "#c2cbdb",
			"accent": "#88c0d0",
			"accent_hover": "#8fbcbb",
			"button_bg": "#5e81ac",
			"button_text": "#eceff4",
			"button_hover_bg": "#81a1c1",
			"border": "#4c566a",
		},
	},
]


def validate_palettes() -> list[str]:
	"""Return a list of human-readable validation errors. Empty list = all good.

	Used by tests and during dev import; never raised at runtime so a typo in
	one palette doesn't take the whole feature offline."""
	errors: list[str] = []
	for p in PALETTES:
		c = p["colors"]
		label = p["label"]
		if not passes_aa(c["text_primary"], c["bg_primary"]):
			errors.append(f"{label}: text_primary on bg_primary fails AA")
		if not passes_aa(c["text_primary"], c["bg_surface"]):
			errors.append(f"{label}: text_primary on bg_surface fails AA")
		if not passes_aa(c["button_text"], c["button_bg"], large_text=True):
			errors.append(f"{label}: button_text on button_bg fails AA-large")
	return errors


def get_palettes() -> list[dict]:
	"""Return the curated palette list as a list of plain dicts for JSON
	serialization. Filters out any palette that fails contrast validation
	so the UI never offers a broken option."""
	bad = {e.split(":", 1)[0] for e in validate_palettes()}
	return [p for p in PALETTES if p["label"] not in bad]
