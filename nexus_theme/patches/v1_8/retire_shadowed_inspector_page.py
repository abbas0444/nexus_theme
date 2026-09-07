import frappe


def execute():
	"""Drop the Page record the app used to register as "permission-inspector".

	Frappe ships a single DocType of its own called "Permission Inspector",
	and the Desk router resolves /app/permission-inspector to that form
	before it looks for a Page of the same name, so the app's page could not
	be reached at that address. The page now lives at
	/app/nexus-permission-inspector; this removes the shadowed record from
	sites that installed the earlier version.
	"""
	if frappe.db.get_value("Page", "permission-inspector", "module") == "Nexus Theme":
		frappe.delete_doc("Page", "permission-inspector", ignore_permissions=True, force=True)
