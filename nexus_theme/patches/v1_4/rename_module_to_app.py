"""Rename the Frappe Module from "Themes" to "Nexus Theme".

The module was renamed to line up with the app's display name. modules.txt
and every DocType JSON already carry the new value; this patch fixes sites
installed under the old name so their `tabModule Def` row and every
DocType's `module` column match the new value — otherwise the old row is
left orphaned after sync_for_app.
"""

import frappe

OLD = "Themes"
NEW = "Nexus Theme"


def execute():
	if not frappe.db.exists("Module Def", OLD):
		# Fresh install — Frappe creates "Nexus Theme" directly.
		return

	if frappe.db.exists("Module Def", NEW):
		# Both rows exist: doctype sync already repointed to NEW, so just
		# repoint anything left and drop the orphaned OLD row.
		_repoint_doctypes()
		frappe.delete_doc("Module Def", OLD, ignore_permissions=True, force=True)
	else:
		frappe.rename_doc("Module Def", OLD, NEW, force=True, merge=False)
		_repoint_doctypes()

	frappe.db.commit()


def _repoint_doctypes():
	frappe.db.sql(
		"UPDATE `tabDocType` SET module = %s WHERE module = %s",
		(NEW, OLD),
	)
