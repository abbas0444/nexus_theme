"""Clean up everything the app created when it is removed.

Without this, uninstalling left the "Theme User" role on every user, the
Navbar Items and the Desktop Icon that install.py registered (a tile that
routes to a page that no longer exists), and the asset tree copied into
sites/assets by install.sync_public_assets(). Frappe drops the app's own
DocTypes and module-owned records; the rest is ours to remove.

Runs `before_uninstall` so the DocTypes are still present while we read
them.
"""

import shutil
from pathlib import Path

import frappe

from nexus_theme.install import NAVBAR_ITEMS, THEME_USER_ROLE


def _remove_theme_user_role() -> None:
	"""Drop the role from every user, then delete the role itself."""
	if not frappe.db.exists("Role", THEME_USER_ROLE):
		return
	try:
		frappe.db.delete("Has Role", {"role": THEME_USER_ROLE})
		frappe.delete_doc("Role", THEME_USER_ROLE, ignore_permissions=True, force=True)
	except Exception:
		frappe.log_error(title="nexus_theme: could not remove Theme User role")


def _remove_synced_assets() -> None:
	"""Remove the asset tree install.sync_public_assets() copied into the bench.

	Deliberately narrow: only the app's own directory under sites/assets, and
	only when it is a real directory rather than the symlink a standard bench
	uses (removing that would delete the app's source `public/` folder).
	"""
	try:
		bench_root = Path(frappe.utils.get_bench_path())
	except Exception:
		return

	target = bench_root / "sites" / "assets" / "nexus_theme"
	try:
		if target.is_symlink() or not target.is_dir():
			return
		if target.name != "nexus_theme":
			return
		shutil.rmtree(target)
	except Exception:
		frappe.log_error(title="nexus_theme: could not remove synced assets")


def _remove_navbar_items() -> None:
	"""Take our entries back out of the sidebar settings dropdown.

	They are Actions calling window.openThemeSwitcher / openSoundStudio —
	guarded, so they would fail silently rather than error, but a menu item
	that does nothing is worse than none.
	"""
	if not frappe.db.exists("DocType", "Navbar Settings"):
		return
	try:
		labels = {item["item_label"] for item in NAVBAR_ITEMS}
		settings = frappe.get_single("Navbar Settings")
		rows = settings.settings_dropdown or []
		keep = [row for row in rows if row.item_label not in labels]
		if len(keep) != len(rows):
			settings.set("settings_dropdown", keep)
			settings.flags.ignore_permissions = True
			settings.save()
	except Exception:
		frappe.log_error(title="nexus_theme: could not remove navbar items")


def _remove_desktop_icon() -> None:
	"""Drop the tile install.ensure_desktop_icon() put on the home grid."""
	if not frappe.db.exists("DocType", "Desktop Icon"):
		return
	try:
		for name in frappe.get_all("Desktop Icon", filters={"app": "nexus_theme"}, pluck="name"):
			frappe.delete_doc("Desktop Icon", name, ignore_permissions=True, force=True)
	except Exception:
		frappe.log_error(title="nexus_theme: could not remove desktop icon")


def before_uninstall() -> None:
	_remove_theme_user_role()
	_remove_navbar_items()
	_remove_desktop_icon()
	_remove_synced_assets()
	frappe.clear_cache()
