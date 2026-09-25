"""Give the new Home Page settings their defaults on existing sites.

Theme Settings is a Single, and a Single keeps one row per field in
tabSingles. Adding a Check with default 1 does not write that row on a site
that already saved the settings, so the field reads back as 0: the form
would show "Show Greeting" and "Show Shortcuts" unticked, and the page
would hide both the moment an admin turned it on. This writes each default
once, only where the field has no stored value at all, so nothing an admin
has already chosen is touched. The page itself stays off (use_nexus_home
defaults to 0, which is also what a missing value reads as).
"""

import frappe

DEFAULTS = {
	"home_show_greeting": 1,
	"home_show_shortcuts": 1,
	"home_layout": "Grid",
}


def execute():
	if not frappe.db.exists("DocType", "Theme Settings"):
		return

	wrote = False
	for field, value in DEFAULTS.items():
		if frappe.db.exists("Singles", {"doctype": "Theme Settings", "field": field}):
			continue
		frappe.db.set_single_value("Theme Settings", field, value)
		wrote = True

	if wrote:
		from nexus_theme.nexus_theme.doctype.theme_settings.theme_settings import (
			clear_settings_cache,
		)

		clear_settings_cache()
