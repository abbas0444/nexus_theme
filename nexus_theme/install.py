"""Provisioning for the "Theme User" role and public asset sync.

Theme Definition and the per-user preference DocTypes are personalized by
every Desk user, so they each grant create/read/write to a role — but that
role must NOT be "All", which also covers Website (portal) users who have no
business touching Desk personalization.

The app therefore ships a dedicated "Theme User" role and grants it to every
System (Desk) user: on install and on every migrate (`provision_theme_user_role`),
and whenever a User is inserted or saved as a System User (`assign_theme_role`,
wired to both `after_insert` and `on_update`). Website users are never granted
it.
"""

import os
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


def _grant_theme_user(user_doc) -> None:
	"""Add the role to a loaded User without a nested save.

	`User.add_roles` appends and calls save(), which re-enters validate and
	on_update — the very hook this is called from. Inserting the child row
	directly sidesteps that; the user's role cache is then dropped so the
	grant is visible on their next request.
	"""
	if any(row.role == THEME_USER_ROLE for row in user_doc.get("roles", [])):
		return
	row = user_doc.append("roles", {"role": THEME_USER_ROLE})
	row.db_insert()
	frappe.clear_cache(user=user_doc.name)


def provision_theme_user_role() -> None:
	"""Ensure the role exists and every System user holds it.

	Idempotent, and cheap enough to run on every migrate: two queries to
	find who is missing it, then one insert per missing user. The previous
	version queried once per user and only ran on install, so a site whose
	users were created before the app never caught up.
	"""
	ensure_theme_user_role()
	system_users = set(frappe.get_all("User", filters={"user_type": "System User"}, pluck="name"))
	holders = set(
		frappe.get_all(
			"Has Role",
			filters={"parenttype": "User", "role": THEME_USER_ROLE},
			pluck="parent",
		)
	)
	for name in sorted(system_users - holders):
		_grant_theme_user(frappe.get_doc("User", name))


def sync_public_assets() -> None:
	"""Make sure `/assets/nexus_theme/...` is served.

	`bench build` links `sites/assets/nexus_theme` to this app's public folder,
	and a Frappe Cloud deploy does the same. `bench install-app` on its own
	does not, so when the link is missing this creates exactly that link. A
	real directory left behind by an older version is refreshed in place.
	Any filesystem problem is ignored: a missing link only affects the look,
	and must never stop an install or a migrate.
	"""
	source_dir = Path(__file__).resolve().parent / "public"
	if not source_dir.exists():
		return

	sites_path = getattr(frappe.local, "sites_path", None)
	assets_root = (
		Path(sites_path).resolve() / "assets"
		if sites_path
		else Path(__file__).resolve().parents[3] / "sites" / "assets"
	)
	target_dir = assets_root / "nexus_theme"

	try:
		if target_dir.is_symlink() or target_dir.exists():
			if target_dir.resolve() == source_dir.resolve():
				return
			if target_dir.is_dir() and not target_dir.is_symlink():
				for path in source_dir.rglob("*"):
					if path.is_file():
						target_path = target_dir / path.relative_to(source_dir)
						target_path.parent.mkdir(parents=True, exist_ok=True)
						shutil.copy2(path, target_path)
			return

		assets_root.mkdir(parents=True, exist_ok=True)
		os.symlink(source_dir, target_dir)
	except OSError:
		return


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


def ensure_desktop_icon() -> None:
	"""Put the app's tile on the Desk home grid. Idempotent.

	Frappe builds these icons from `add_to_apps_screen`, but only inside
	`frappe.utils.install`, which runs when a *site* is created. An app
	installed later onto an existing site therefore never gets a tile —
	so we create ours here instead of waiting for the next new site.

	`label` is the Desktop Icon autoname, so an icon of any type already
	holding "Nexus Theme" (a workspace tile, say) means there is nothing
	to add.
	"""
	if not frappe.db.exists("DocType", "Desktop Icon"):
		return
	try:
		screen = frappe.get_hooks("add_to_apps_screen", app_name="nexus_theme")
		if not screen:
			return
		entry = screen[0]
		label = entry.get("title") or "Nexus Theme"
		if frappe.db.exists("Desktop Icon", label):
			return

		icon = frappe.new_doc("Desktop Icon")
		icon.label = label
		icon.link_type = "External"
		icon.icon_type = "App"
		icon.app = "nexus_theme"
		icon.link = entry.get("route")
		icon.logo_url = entry.get("logo")
		icon.insert(ignore_permissions=True, ignore_if_duplicate=True)

		from frappe.desk.doctype.desktop_icon.desktop_icon import clear_desktop_icons_cache

		clear_desktop_icons_cache()
	except Exception:
		# A missing tile costs the user an icon; raising here would abort
		# the whole install or migrate.
		frappe.log_error(title="nexus_theme: could not add desktop icon")


def after_install() -> None:
	"""Run once on `bench install-app`."""
	provision_theme_user_role()
	sync_public_assets()
	ensure_navbar_items()
	ensure_desktop_icon()


def after_migrate() -> None:
	"""Run after migrate so every provisioned thing stays in place after upgrades."""
	provision_theme_user_role()
	sync_public_assets()
	ensure_navbar_items()
	ensure_desktop_icon()


def assign_theme_role(doc, method=None) -> None:
	"""doc_event on User (after_insert and on_update): grant the role to Desk users.

	after_insert alone was not enough. Frappe's User.validate() derives
	user_type from the roles present, so a user created without a Desk role
	is a Website User at insert time and gets nothing — and when a Desk role
	is added later, the promotion to System User happens on a save this hook
	never saw. Watching on_update as well catches it. Both checks are
	in-memory, so the common case costs no query.
	"""
	if doc.user_type != "System User":
		return
	if any(row.role == THEME_USER_ROLE for row in doc.get("roles", [])):
		return
	ensure_theme_user_role()
	_grant_theme_user(doc)
