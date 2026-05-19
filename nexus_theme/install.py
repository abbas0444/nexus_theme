"""Provisioning for the "Theme User" role.

Theme Definition and the per-user preference DocTypes are personalized by
every Desk user, so they each grant create/read/write to a role — but that
role must NOT be "All", which also covers Website (portal) users who have no
business touching Desk personalization.

The app therefore ships a dedicated "Theme User" role and grants it to every
System (Desk) user: on install (`after_install`), on upgrade (patch v1_5), and
whenever a new user is created (`doc_events` on User). Website users are never
granted it.
"""

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


def after_install() -> None:
	"""Run once on `bench install-app`."""
	provision_theme_user_role()


def assign_theme_role(doc, method=None) -> None:
	"""doc_event (User.after_insert): grant the role to new Desk users only."""
	if doc.user_type != "System User":
		return
	ensure_theme_user_role()
	if not any(row.role == THEME_USER_ROLE for row in doc.get("roles", [])):
		doc.add_roles(THEME_USER_ROLE)
