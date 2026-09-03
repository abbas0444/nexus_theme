"""Clean up everything the app created when it is removed.

Without this, uninstalling left the "Theme User" role on every user, all
per-user preference rows, and the asset tree copied into sites/assets by
install.sync_public_assets(). Frappe drops the app's own DocTypes, but the
role and the copied files are ours to remove.

Runs `before_uninstall` so the DocTypes are still present while we read
them.
"""

import shutil
from pathlib import Path

import frappe

from nexus_theme.install import THEME_USER_ROLE


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


def before_uninstall() -> None:
	_remove_theme_user_role()
	_remove_synced_assets()
	frappe.clear_cache()
