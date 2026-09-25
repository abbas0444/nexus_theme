"""The three density modes and how a user's is resolved.

Density is how much vertical room the Desk gives each row, field and
button: Compact for people who want more on screen, Spacious for people
who want more air, Comfortable for what Frappe draws on its own. It is
independent of the theme — a person on Frappe's stock look can be Compact,
and the density survives a theme being deleted.

Two places may hold a choice. The user's own row (User Theme Preference)
wins when it has one; empty there means "follow the site", and the site's
answer is the default_density on Theme Settings, which is Comfortable
until an admin changes it. So the order is user, then site, then
Comfortable — and Comfortable is what an untouched site looks like.

Stored values are the Select labels ("Compact"); the client and the API
speak in keys ("compact"). Both spellings are accepted on the way in.

This module is intentionally free of any `frappe` import so it stays pure
and unit-testable; api.set_density does the throwing.
"""

# One entry per mode, in the order the UI shows them. The client keeps the
# same list in density.js (NexusDensity.modes()) — keep the two the same.
MODES = (
	{
		"key": "compact",
		"label": "Compact",
		"description": "Tighter rows and fields, so more fits on screen.",
	},
	{
		"key": "comfortable",
		"label": "Comfortable",
		"description": "Frappe's own spacing.",
	},
	{
		"key": "spacious",
		"label": "Spacious",
		"description": "More room around rows and fields.",
	},
)

DEFAULT_DENSITY = "comfortable"

_BY_KEY = {m["key"]: m for m in MODES}
_KEY_BY_LOWER_LABEL = {m["label"].lower(): m["key"] for m in MODES}


def normalize_density(value) -> str | None:
	"""The mode key for `value`, or None if it names no mode.

	Takes a key ("compact"), a label ("Compact"), either with stray case or
	whitespace, and nothing else. None and "" give None: an empty choice is
	a real state (follow the site), not an error, so the caller decides
	what to make of it.
	"""
	if value is None:
		return None
	text = str(value).strip().lower()
	if not text:
		return None
	if text in _BY_KEY:
		return text
	return _KEY_BY_LOWER_LABEL.get(text)


def label_for(key: str) -> str:
	"""The Select label stored for a mode key. Raises KeyError for a stranger."""
	return _BY_KEY[key]["label"]


def resolve_density(user_value=None, site_value=None) -> tuple[str, str]:
	"""(key, source) for a user given their own value and the site's.

	`source` says which one answered: "user", "site_default" or "default".
	A value that names no mode counts as absent, so a stale or mistyped
	one falls through rather than breaking the boot.
	"""
	user_key = normalize_density(user_value)
	if user_key:
		return user_key, "user"
	site_key = normalize_density(site_value)
	if site_key:
		return site_key, "site_default"
	return DEFAULT_DENSITY, "default"
