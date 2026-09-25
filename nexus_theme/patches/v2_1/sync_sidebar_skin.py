"""Give the bundled themes their sidebar skin on sites that already have them.

On an ordinary migrate the fixture sync that runs after the patches already
rewrites every bundled theme from fixtures/theme_definition.json, sidebar
fields included. This patch is for the migrate that skips it
(`bench migrate --skip-fixtures`): without it the new columns would sit at
their defaults — Plain, no pattern, no tints — on every bundled theme.

Only rows still flagged `is_default` are touched, and only while their
sidebar fields are still untouched, so a System Manager who has already set
a sidebar on a bundled theme keeps it. Custom themes are never read.
"""

import os

import frappe

SIDEBAR_FIELDS = (
	"sidebar_style",
	"sidebar_bg",
	"sidebar_text",
	"sidebar_active_bg",
	"sidebar_pattern",
	"icon_tints",
)


def _untouched(doc) -> bool:
	if (doc.sidebar_style or "Plain") != "Plain":
		return False
	if doc.sidebar_bg or doc.sidebar_text or doc.sidebar_active_bg:
		return False
	return not (doc.sidebar_pattern or doc.icon_tints)


def execute():
	fixture_path = frappe.get_app_path("nexus_theme", "fixtures", "theme_definition.json")
	if not os.path.exists(fixture_path):
		return

	updated = 0
	for theme in frappe.get_file_json(fixture_path):
		name = theme.get("name") or theme.get("theme_key")
		if not name or not frappe.db.exists("Theme Definition", name):
			continue

		doc = frappe.get_doc("Theme Definition", name)
		if not doc.is_default or not _untouched(doc):
			continue

		changed = False
		for field in SIDEBAR_FIELDS:
			if field in theme and doc.get(field) != theme[field]:
				doc.set(field, theme[field])
				changed = True
		if not changed:
			continue

		try:
			doc.save(ignore_permissions=True)
			updated += 1
		except Exception:
			# validate() throws when the sidebar would fail WCAG AA — possible
			# if this theme's accent was edited on the site. It stays Plain.
			frappe.log_error(
				title="nexus_theme: could not apply sidebar skin",
				message=f"Theme Definition {name}",
			)

	if updated:
		# Active themes are read into bootinfo per user.
		frappe.clear_cache()

	frappe.db.commit()
