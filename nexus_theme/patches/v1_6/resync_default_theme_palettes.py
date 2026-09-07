"""Push the redesigned palettes onto default themes that already exist.

The v1_0 / v1_1 seeder is insert-only — it skips any Theme Definition whose
name is already present. That is correct for keeping user edits, but it also
means a site installed before this release keeps the old colors and fonts
forever: the fixture changes, nothing on disk disagrees, and no row is
touched. This patch closes that gap by writing the fixture's visual fields
back onto the shipped themes.

Only rows still flagged `is_default` are updated, and only presentation
fields — ownership, sharing and the theme key are left exactly as they are.
A theme someone converted into their own custom theme is skipped entirely.
"""

import os

import frappe

# Presentation only. Deliberately excludes name / theme_key (identity),
# is_default / is_public / owner_user (ownership and visibility).
SYNCED_FIELDS = (
	"theme_name",
	"is_dark",
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
	"font_family",
	"font_size_base",
	"font_weight_base",
	"transition_duration",
	"enable_hover_lift",
	"border_radius",
)


def execute():
	fixture_path = frappe.get_app_path("nexus_theme", "fixtures", "theme_definition.json")
	if not os.path.exists(fixture_path):
		return

	themes = frappe.get_file_json(fixture_path)
	updated = 0

	for theme in themes:
		name = theme.get("name") or theme.get("theme_key")
		if not name or not frappe.db.exists("Theme Definition", name):
			continue

		doc = frappe.get_doc("Theme Definition", name)
		if not doc.is_default:
			# No longer a shipped theme — someone took it over. Leave it.
			continue

		changed = False
		for field in SYNCED_FIELDS:
			if field in theme and doc.get(field) != theme[field]:
				doc.set(field, theme[field])
				changed = True
		if not changed:
			continue

		try:
			doc.save(ignore_permissions=True)
			updated += 1
		except Exception:
			# validate() throws on a default theme that fails WCAG AA. Log and
			# carry on rather than aborting the whole migrate over a palette.
			frappe.log_error(
				title="nexus_theme: could not resync theme",
				message=f"Theme Definition {name}",
			)

	if updated:
		# Active themes are read into bootinfo per user, so the cached copies
		# still hold the old colors until they are dropped.
		frappe.clear_cache()

	frappe.db.commit()
