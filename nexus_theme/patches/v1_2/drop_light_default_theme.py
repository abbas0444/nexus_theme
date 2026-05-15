import frappe


def execute():
	"""Drop the bundled `light-default` theme so Theme Studio is opt-in.

	Frappe ships its own native light/dark toggle (`data-theme-mode`). The
	old `light-default` Theme Definition duplicated that and meant any user
	who applied it from Theme Studio would have their CSS variables override
	Frappe's native toggle indefinitely. Removing it lets users fall back to
	Frappe's native theme by default; they can still create custom themes
	via Theme Studio if they want to override.
	"""
	users_reverted = frappe.db.count(
		"User Theme Preference", {"active_theme": "light-default"}
	)
	if users_reverted:
		frappe.db.delete("User Theme Preference", {"active_theme": "light-default"})

	if frappe.db.exists("Theme Definition", "light-default"):
		# `on_trash` blocks deletion of default themes, so clear the flag in
		# the DB first to avoid triggering the guard.
		frappe.db.set_value("Theme Definition", "light-default", "is_default", 0)
		doc = frappe.get_doc("Theme Definition", "light-default")
		doc.flags.ignore_links = 1
		doc.flags.ignore_permissions = 1
		doc.delete()

	frappe.db.commit()
