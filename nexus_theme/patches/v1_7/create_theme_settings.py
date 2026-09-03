"""Materialise the Theme Settings single with backwards-compatible defaults.

The DocType is new, so existing sites have no row. `get_settings()` already
falls back to permissive defaults when the row is missing, but creating it
explicitly means an admin opening the page sees the real current behaviour
rather than an empty form.

Deliberately does NOT set a site default theme: doing so would change what
users with no preference see, and this app's rule is that a fresh user gets
stock Frappe until someone chooses otherwise.
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Theme Settings"):
		return

	doc = frappe.get_single("Theme Settings")

	# Only stamp defaults on a row that has never been saved, so an admin who
	# already configured this on a newer install is never overwritten.
	if doc.get("__islocal") or not frappe.db.exists(
		"Singles", {"doctype": "Theme Settings", "field": "allow_custom_themes"}
	):
		doc.allow_custom_themes = 1
		doc.allow_public_sharing = 1
		doc.allow_user_sounds = 1
		doc.restrict_theme_choice = 0
		doc.apply_to_website = 0
		doc.flags.ignore_permissions = True
		doc.save()

	frappe.db.commit()
