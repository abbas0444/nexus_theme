"""Provisioning for the "Theme User" role and public asset sync.

Theme Definition and the per-user preference DocTypes are personalized by
every Desk user, so they each grant create/read/write to a role — but that
role must NOT be "All", which also covers Website (portal) users who have no
business touching Desk personalization.

The app therefore ships a dedicated "Theme User" role and grants it to every
System (Desk) user: on install (`after_install`), on upgrade (patch v1_5), and
whenever a new user is created (`doc_events` on User). Website users are never
granted it.
"""

import shutil
from pathlib import Path

import frappe

THEME_USER_ROLE = "Theme User"


def ensure_theme_user_role() -> None:
	"""Create the "Theme User" role if it does not already exist."""
	if frappe.db.exists("Role", THEME_USER_ROLE):
		return
	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": THEME_USER_ROLE,
			"desk_access": 1,
		}
	).insert(ignore_permissions=True)


def provision_theme_user_role() -> None:
	"""Ensure the role exists and every System user holds it.

	Idempotent — safe to run on install and on every migrate.
	"""
	ensure_theme_user_role()
	for user in frappe.get_all("User", filters={"user_type": "System User"}, pluck="name"):
		if frappe.db.exists("Has Role", {"parent": user, "role": THEME_USER_ROLE}):
			continue
		frappe.get_doc("User", user).add_roles(THEME_USER_ROLE)


def sync_public_assets() -> None:
	"""Copy the app's public assets into the bench's shared sites/assets tree.

	Frappe 16 will then serve the files from `/assets/nexus_theme/...`
	even when the app's public files are not already copied by the default
	build pipeline.
	"""
	source_dir = Path(__file__).resolve().parent / "public"
	if not source_dir.exists():
		return

	bench_root = Path(__file__).resolve().parents[3]
	target_dir = bench_root / "sites" / "assets" / "nexus_theme"

	try:
		if target_dir.resolve() == source_dir.resolve():
			return
	except FileNotFoundError:
		pass

	target_dir.mkdir(parents=True, exist_ok=True)

	for path in source_dir.rglob("*"):
		if not path.is_file():
			continue
		rel_path = path.relative_to(source_dir)
		target_path = target_dir / rel_path
		if target_path.resolve() == path.resolve():
			continue
		target_path.parent.mkdir(parents=True, exist_ok=True)
		shutil.copy2(path, target_path)


# Entries added to the sidebar's settings dropdown. Frappe v16 replaced the
# top navbar with the left sidebar, so the app's own DOM injection (which
# targets `.navbar-nav` and the v15 user dropdown) no longer finds anything
# and Theme Studio / Sound Studio had no reachable entry point at all.
#
# Navbar Settings is the supported way in: sidebar_header.add_navbar_items()
# reads `settings_dropdown` and renders each item. It is also how Frappe
# itself registers "Toggle Theme".
NAVBAR_ITEMS = (
	{
		"item_label": "Theme Studio",
		"item_type": "Action",
		"action": "window.openThemeSwitcher && window.openThemeSwitcher()",
		"is_standard": 1,
	},
	{
		"item_label": "Sound Settings",
		"item_type": "Action",
		"action": "window.openSoundStudio && window.openSoundStudio()",
		"is_standard": 1,
	},
)


def ensure_navbar_items() -> None:
	"""Add our entries to the sidebar settings dropdown. Idempotent."""
	if not frappe.db.exists("DocType", "Navbar Settings"):
		return
	try:
		settings = frappe.get_single("Navbar Settings")
		existing = {row.item_label for row in (settings.settings_dropdown or [])}
		added = False
		for item in NAVBAR_ITEMS:
			if item["item_label"] in existing:
				continue
			settings.append("settings_dropdown", dict(item))
			added = True
		if added:
			settings.flags.ignore_permissions = True
			settings.save()
	except Exception:
		# A missing entry costs the user a menu link; a raised exception here
		# would abort the whole install or migrate.
		frappe.log_error(title="nexus_theme: could not add navbar items")


def after_install() -> None:
	"""Run once on `bench install-app`."""
	provision_theme_user_role()
	sync_public_assets()
	ensure_navbar_items()


def after_migrate() -> None:
	"""Run after migrate so the public assets stay available after upgrades."""
	sync_public_assets()
	ensure_navbar_items()


def assign_theme_role(doc, method=None) -> None:
	"""doc_event (User.after_insert): grant the role to new Desk users only."""
	if doc.user_type != "System User":
		return
	ensure_theme_user_role()
	if not any(row.role == THEME_USER_ROLE for row in doc.get("roles", [])):
		doc.add_roles(THEME_USER_ROLE)
