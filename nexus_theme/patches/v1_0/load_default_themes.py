import os

import frappe


def execute():
	"""Seed the 10 shipped Theme Definition records on first migrate.

	Idempotent: records already present are left untouched; missing ones are
	inserted. This keeps default themes synced even if fixtures get out of
	step with the database.
	"""
	fixture_path = frappe.get_app_path("nexus_theme", "fixtures", "theme_definition.json")
	if not os.path.exists(fixture_path):
		return

	# Read via Frappe's helper rather than a raw open() — the path is built
	# entirely from app-relative constants, so there is no traversal surface.
	themes = frappe.get_file_json(fixture_path)

	for theme in themes:
		name = theme.get("name") or theme.get("theme_key")
		if not name:
			continue
		if frappe.db.exists("Theme Definition", name):
			continue
		doc = frappe.get_doc(theme)
		doc.insert(ignore_permissions=True)

	frappe.db.commit()
