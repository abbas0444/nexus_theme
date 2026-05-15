"""Rename the app module from "THemes" to "Themes".

The module was originally created with an unintended capital H. The source
files (modules.txt, every DocType JSON) are already updated. This patch
catches sites that were installed under the old name so their
`tabModule Def` row and every DocType's `module` column line up with the
new value — otherwise the next sync_for_app errors with
"Module Def THemes not found".
"""

import frappe


OLD = "THemes"
NEW = "Themes"


def execute():
	if not frappe.db.exists("Module Def", OLD):
		# Fresh install — Frappe will create "Themes" directly. Nothing to do.
		return

	if frappe.db.exists("Module Def", NEW):
		# Both rows exist (unlikely, but safe): repoint everything to NEW and
		# drop the OLD row.
		_repoint_doctypes()
		frappe.delete_doc("Module Def", OLD, ignore_permissions=True, force=True)
	else:
		# Rename the Module Def row, then repoint every DocType that still
		# carries the old module name.
		frappe.rename_doc("Module Def", OLD, NEW, force=True, merge=False)
		_repoint_doctypes()

	frappe.db.commit()


def _repoint_doctypes():
	frappe.db.sql(
		"UPDATE `tabDocType` SET module = %s WHERE module = %s",
		(NEW, OLD),
	)
