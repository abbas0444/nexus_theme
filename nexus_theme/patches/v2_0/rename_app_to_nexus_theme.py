"""Rename the Frappe Module from "Nexus Theme" to "Nexus Theme".

The app was renamed from `nexus_theme` to `nexus_theme`, which moves
its display name — and therefore its Module Def — with it. modules.txt and
every DocType JSON already carry the new value; this patch fixes sites
installed under the old name so their `tabModule Def` row and every DocType's
`module` column match, otherwise the old row is left orphaned after
sync_for_app.

The `tabInstalled Application` row is repointed here too: it stores the
Python package name, which no longer resolves under the old value.
"""

import frappe

OLD = "Nexus Theme"
NEW = "Nexus Theme"

OLD_APP = "nexus_theme"
NEW_APP = "nexus_theme"


def execute():
	_rename_module()
	_rename_installed_app()
	frappe.db.commit()


def _rename_module():
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

	frappe.db.set_value("Module Def", NEW, "app_name", NEW_APP)


def _repoint_doctypes():
	frappe.db.sql(
		"UPDATE `tabDocType` SET module = %s WHERE module = %s",
		(NEW, OLD),
	)


def _rename_installed_app():
	"""Point the Installed Application row at the new package name."""
	if not frappe.db.exists("DocType", "Installed Application"):
		return
	frappe.db.sql(
		"UPDATE `tabInstalled Application` SET app_name = %s WHERE app_name = %s",
		(NEW_APP, OLD_APP),
	)
