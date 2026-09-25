"""Pure rules behind the Nexus Home page.

The page greets the person, offers a few shortcuts and lays out one tile
per workspace they can already open. Which workspaces those are is
Frappe's call (api.get_home_data asks the same function the Desk sidebar
uses); what this module decides is how that list is shaped into tiles, how
open to-dos are counted per tile, which colour each tile gets and which
greeting fits the hour.

This module is intentionally free of any `frappe` import so it stays pure
and unit-testable, like utils/density.py.
"""

# The Page record that holds the home screen, and so its /app/<name> route.
HOME_PAGE = "nexus-home"

# Number of tints in the palette nexus_home.css defines (.nxh-tint-0 …
# .nxh-tint-7). Keep the two the same.
TINT_COUNT = 8

# Select labels on Theme Settings → the key the page and its CSS use.
LAYOUTS = {"grid": "Grid", "list": "Compact list"}
DEFAULT_LAYOUT = "grid"


def normalize_layout(value) -> str:
	"""A layout key ("grid" or "list") from a stored label or a key.

	Anything unknown, empty included, is the grid: it is the default, and a
	half-migrated site must still draw something sensible.
	"""
	text = str(value or "").strip().lower()
	if not text:
		return DEFAULT_LAYOUT
	for key, label in LAYOUTS.items():
		if text in (key, label.lower()):
			return key
	return DEFAULT_LAYOUT


def greeting_bucket(hour: int) -> str:
	"""Which greeting fits an hour of the day, 0-23.

	The page itself greets by the browser's clock (nexus_home.js keeps the
	same boundaries); this mirror exists so the rule has one tested
	statement. Before noon is morning, before six in the evening is
	afternoon, the rest is evening — midnight to five included, because
	"Good morning" at 2 a.m. reads as a joke.
	"""
	try:
		hour = int(hour)
	except Exception:
		# Not a number at all: pick the first bucket rather than fail a
		# greeting over it.
		return "morning"
	hour %= 24
	if 5 <= hour < 12:
		return "morning"
	if 12 <= hour < 18:
		return "afternoon"
	return "evening"


def tint_index(name: str, count: int = TINT_COUNT) -> int:
	"""A stable palette slot for a tile, from its name.

	Python's own hash() is salted per process, so the same workspace would
	change colour on every restart. This is a plain 31-multiplier string
	hash kept to 32 bits — the same one nexus_home.js falls back to when
	the server's value is missing — so a tile keeps its colour everywhere.
	"""
	h = 0
	for ch in str(name or ""):
		h = (h * 31 + ord(ch)) & 0xFFFFFFFF
	return h % max(int(count or 1), 1)


def first_name_for(first_name, full_name, user) -> str:
	"""The name to greet someone by: first name, else the first word of the
	full name, else the part of the login before any "@"."""
	words = str(full_name or "").split()
	for candidate in (first_name, words[0] if words else None):
		text = str(candidate or "").strip()
		if text:
			return text
	return str(user or "").split("@")[0]


def counts_by_module(todo_counts: dict, doctype_modules: dict) -> dict:
	"""Open to-dos per module.

	`todo_counts` maps a to-do's reference DocType to how many open to-dos
	point at it; `doctype_modules` maps DocType → module. To-dos about a
	DocType with no known module are left out rather than guessed at.
	"""
	out: dict = {}
	for doctype, n in (todo_counts or {}).items():
		module = (doctype_modules or {}).get(doctype)
		if not module or not n:
			continue
		out[module] = out.get(module, 0) + int(n)
	return out


def build_tiles(pages, module_counts: dict | None = None, user: str | None = None) -> list[dict]:
	"""Shape the Desk's own workspace list into home tiles.

	`pages` is what Frappe's sidebar builder returns — already filtered to
	the workspaces this user may open, so nothing here widens access; it
	only narrows. Hidden workspaces and child workspaces (the ones nested
	under another in the sidebar) are skipped, as is anyone else's private
	workspace. A workspace listed twice keeps its first entry.

	Each tile carries what the page needs to draw a link: name, label,
	whether it is public (the route differs), the icon name, the open to-do
	count for its module and a tint slot. Frappe 16's "Link" and "URL"
	workspaces carry their target as well, since their sidebar entry opens
	that target rather than a workspace.
	"""
	module_counts = module_counts or {}
	tiles = []
	seen = set()
	for page in pages or []:
		get = page.get if hasattr(page, "get") else (lambda k, _p=page: getattr(_p, k, None))
		name = get("name")
		if not name or name in seen:
			continue
		if get("is_hidden") or get("parent_page"):
			continue
		public = bool(get("public"))
		if not public and user and get("for_user") and get("for_user") != user:
			continue
		seen.add(name)
		module = get("module") or None
		kind = get("type") or "Workspace"
		tile = {
			"name": name,
			"title": get("title") or name,
			"label": get("label") or get("title") or name,
			"public": 1 if public else 0,
			"icon": get("icon") or None,
			"module": module,
			"count": int(module_counts.get(module, 0)) if module else 0,
			"tint": tint_index(name),
			"type": kind,
		}
		if kind == "Link":
			tile["link_type"] = get("link_type") or None
			tile["link_to"] = get("link_to") or None
			# Frappe 16 adds {report_type, ref_doctype} to a workspace that
			# links to a report; the route depends on the report's kind.
			if tile["link_type"] == "Report" and isinstance(get("report"), dict):
				tile["report"] = dict(get("report"))
		elif kind == "URL":
			tile["external_link"] = get("external_link") or None
		tiles.append(tile)
	return tiles
