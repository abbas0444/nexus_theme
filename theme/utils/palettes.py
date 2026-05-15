"""Curated theme palettes for the Theme Studio "Recommended" panel.

Each palette is a complete, WCAG-AA-validated set of the 11 color tokens
that Theme Definition uses, plus a key, label, and dark flag. The frontend
applies a palette by previewing it through ThemeManager.previewOverrides()
exactly the way the editor's color pickers do — no schema changes needed.

To add or modify a palette, keep these invariants:
  * text_primary on bg_primary  passes AA (>= 4.5:1)
  * text_primary on bg_surface  passes AA (>= 4.5:1)
  * button_text  on button_bg   passes AA-large (>= 3.0:1)

The validate_palettes() function below enforces these on import in dev.
"""

from theme.utils.contrast import passes_aa


PALETTES = [
	# ---------- LIGHT ----------
	{
		"key": "indigo-mist",
		"label": "Indigo Mist",
		"category": "Light",
		"is_dark": 0,
		"description": "Calm whites with deep indigo accents. Reads as classic enterprise.",
		"colors": {
			"bg_primary": "#ffffff",
			"bg_surface": "#f8fafc",
			"bg_input": "#ffffff",
			"text_primary": "#0f172a",
			"text_muted": "#475569",
			"accent": "#4f46e5",
			"accent_hover": "#4338ca",
			"button_bg": "#4f46e5",
			"button_text": "#ffffff",
			"button_hover_bg": "#4338ca",
			"border": "#e2e8f0",
		},
	},
	{
		"key": "forest-paper",
		"label": "Forest Paper",
		"category": "Light",
		"is_dark": 0,
		"description": "Cream paper, deep evergreen. Warm, focused, easy on long reads.",
		"colors": {
			"bg_primary": "#fdfcf7",
			"bg_surface": "#f5f3ea",
			"bg_input": "#ffffff",
			"text_primary": "#1c2a1d",
			"text_muted": "#4a5d4c",
			"accent": "#15803d",
			"accent_hover": "#166534",
			"button_bg": "#15803d",
			"button_text": "#ffffff",
			"button_hover_bg": "#166534",
			"border": "#e7e3d4",
		},
	},
	{
		"key": "rose-quartz",
		"label": "Rose Quartz",
		"category": "Light",
		"is_dark": 0,
		"description": "Soft pinks with warm charcoal text. Friendly without being childish.",
		"colors": {
			"bg_primary": "#fff7f7",
			"bg_surface": "#ffeaea",
			"bg_input": "#ffffff",
			"text_primary": "#3f1d1d",
			"text_muted": "#7a3939",
			"accent": "#be123c",
			"accent_hover": "#9f1239",
			"button_bg": "#be123c",
			"button_text": "#ffffff",
			"button_hover_bg": "#9f1239",
			"border": "#fcd9d9",
		},
	},
	{
		"key": "graphite-amber",
		"label": "Graphite Amber",
		"category": "Light",
		"is_dark": 0,
		"description": "Neutral grays with amber CTAs. High contrast, all-business.",
		"colors": {
			"bg_primary": "#fafafa",
			"bg_surface": "#f4f4f5",
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
			"bg_primary": "#0b1020",
			"bg_surface": "#151a2e",
			"bg_input": "#1c2240",
			"text_primary": "#e8eaf6",
			"text_muted": "#a4adcf",
			"accent": "#a78bfa",
			"accent_hover": "#c4b5fd",
			"button_bg": "#7c3aed",
			"button_text": "#ffffff",
			"button_hover_bg": "#6d28d9",
			"border": "#2a3055",
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
			"bg_surface": "#1a1f24",
			"bg_input": "#22282e",
			"text_primary": "#e6edf3",
			"text_muted": "#9aa6b2",
			"accent": "#2dd4bf",
			"accent_hover": "#5eead4",
			"button_bg": "#0d9488",
			"button_text": "#ffffff",
			"button_hover_bg": "#0f766e",
			"border": "#2a3137",
		},
	},
	{
		"key": "obsidian-rose",
		"label": "Obsidian Rose",
		"category": "Dark",
		"is_dark": 1,
		"description": "Near-black with rose accents. Bold, modern, attention-grabbing.",
		"colors": {
			"bg_primary": "#0a0a0b",
			"bg_surface": "#161618",
			"bg_input": "#1f1f22",
			"text_primary": "#f5f5f7",
			"text_muted": "#a1a1aa",
			"accent": "#f472b6",
			"accent_hover": "#f9a8d4",
			"button_bg": "#db2777",
			"button_text": "#ffffff",
			"button_hover_bg": "#be185d",
			"border": "#27272a",
		},
	},
	{
		"key": "nordic-frost",
		"label": "Nordic Frost",
		"category": "Dark",
		"is_dark": 1,
		"description": "Cool slate with icy blue accents. Crisp, professional, easy on eyes.",
		"colors": {
			"bg_primary": "#1e293b",
			"bg_surface": "#293548",
			"bg_input": "#334155",
			"text_primary": "#f1f5f9",
			"text_muted": "#b6c2d3",
			"accent": "#7dd3fc",
			"accent_hover": "#bae6fd",
			"button_bg": "#0284c7",
			"button_text": "#ffffff",
			"button_hover_bg": "#0369a1",
			"border": "#3f4d63",
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
