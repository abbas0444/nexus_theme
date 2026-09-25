"""What changed in this release, told to each person once.

A release that adds a screen nobody knows about may as well not have
shipped. So the Desk shows a short "What's new" card the first time a
person signs in after an upgrade, and then not again until the next
release that has something to say.

The notes live here, in code, next to the version they describe, rather
than in a DocType: they are part of the release, they are the same on
every site, and a site should never be able to lose or edit them. The
README and the wiki carry the long form; this is the two-minute version.

Only the *series* counts — "2.0" for 2.0.0, 2.0.1 and 2.0.3 alike. A
patch release fixes things; it does not interrupt anyone with a card.
"""

import frappe
from frappe import _

# Newest first. Each entry: the version that introduced it, a title, and
# a handful of items. An item may name a `command` — a JavaScript global
# the card can call to take the person straight to the feature — and the
# card only shows that button when the global exists on the page.
RELEASES = [
	{
		"version": "2.0.0",
		"title": "Nexus Theme 2.0",
		"summary": "Two things people asked for most: a command palette, and room to breathe — or less of it.",
		"items": [
			{
				"heading": "Command Palette",
				"text": "Press Ctrl+K (⌘K on a Mac) anywhere on the Desk. Type a few letters to open any record type, report, page or workspace, jump to something you had open recently, search documents, switch your theme or density, or open the studios — without touching the mouse.",
				"command": "openCommandPalette",
				"command_label": "Try it now",
			},
			{
				"heading": "Density modes",
				"text": "Compact, Comfortable or Spacious. Compact fits more rows on a screen for people who live in lists and grids; Spacious gives forms more air. Set it in Theme Studio or from the command palette; it is yours alone, and an administrator can pick the site's starting point in Theme Settings.",
				"command": "openThemeSwitcher",
				"command_label": "Open Theme Studio",
			},
			{
				"heading": "Under the hood",
				"text": "Automatic light/dark keeps separate colour tweaks for each half. Custom sounds play from the first page load. Toasts stay readable on dark themes. And a long list of smaller fixes — see the release notes.",
			},
		],
	},
]


def series(version: str | None) -> tuple[int, int] | None:
	"""The (major, minor) pair of a version string, or None if it has none.

	Tolerates whatever a stored default might hold — an empty string, an
	old value with only one number, a stray suffix like "2.0.0-beta".
	"""
	if not version:
		return None
	parts = str(version).strip().split(".")
	try:
		major = int(parts[0])
		minor = int(parts[1]) if len(parts) > 1 else 0
	except (TypeError, ValueError):
		return None
	return (major, minor)


def notes_for(version: str) -> dict | None:
	"""The release entry whose series matches `version`, if any."""
	want = series(version)
	if not want:
		return None
	for release in RELEASES:
		if series(release["version"]) == want:
			return release
	return None


def is_new_to(seen_version: str | None, current_version: str) -> bool:
	"""True when the person has not yet seen this series.

	Someone who has seen 2.0.0 is not shown 2.0.1. Someone who has never
	been shown anything is shown the current one, but only if it has notes:
	a fresh install on a version with nothing to say stays quiet.
	"""
	current = series(current_version)
	if not current or not notes_for(current_version):
		return False
	seen = series(seen_version)
	return seen is None or seen < current


SEEN_KEY = "nexus_theme_seen_version"


def current_version() -> str:
	from nexus_theme import __version__

	return __version__


def boot_payload() -> dict:
	"""What the Desk needs to decide whether to show the card, and what on it."""
	version = current_version()
	seen = frappe.defaults.get_user_default(SEEN_KEY)
	show = is_new_to(seen, version)
	return {
		"version": version,
		"seen_version": seen,
		"show": 1 if show else 0,
		"notes": _translated(notes_for(version)) if show else None,
	}


def _translated(release: dict | None) -> dict | None:
	if not release:
		return None
	return {
		"version": release["version"],
		"title": _(release["title"]),
		"summary": _(release["summary"]),
		"items": [
			{
				"heading": _(item["heading"]),
				"text": _(item["text"]),
				"command": item.get("command"),
				"command_label": _(item["command_label"]) if item.get("command_label") else None,
			}
			for item in release["items"]
		],
	}


@frappe.whitelist()
def mark_seen(version: str | None = None) -> dict:
	"""Remember that the signed-in person has seen the card for `version`.

	Defaults to the running version. Stored as a user default, which is
	per person and survives every cache clear; the value is checked with
	series() before it is stored so a client cannot plant anything odd.
	"""
	version = version or current_version()
	if not series(version):
		frappe.throw(_("Not a version: {0}").format(frappe.bold(str(version)[:40])))
	frappe.defaults.set_user_default(SEEN_KEY, str(version).strip())
	# bootinfo is cached per user and carries `show`; without this the
	# card would come back on the next page load until something else
	# happened to clear that cache.
	from nexus_theme.api import _invalidate_bootinfo

	_invalidate_bootinfo()
	return {"seen_version": str(version).strip()}


@frappe.whitelist()
def get_notes(version: str | None = None) -> dict | None:
	"""The notes for a version series, for a "What's new" the person asked to see again."""
	return _translated(notes_for(version or current_version()))
