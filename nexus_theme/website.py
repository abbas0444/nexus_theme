"""Extend the theme past the Desk onto the login page and public website.

The Desk gets its theme from `boot_session`, which needs a logged-in user.
The login page has no user by definition, so nothing themed it — a branded
Desk sat behind a stock Frappe login, which is the most visible unfinished
edge in the app.

This hook resolves the site default theme (only when an admin has opted in
via Theme Settings) and injects it as CSS custom properties in <head>, the
same variable names the Desk stylesheet uses. Purely additive: with no site
default, or with "Apply to Login & Website" off, nothing is emitted and the
website renders exactly as before.
"""

import frappe

from nexus_theme.utils.web_css import VAR_MAP, theme_css_rules


def update_website_context(context):
	"""`update_website_context` hook — theme the login page and website."""
	try:
		from nexus_theme.nexus_theme.doctype.theme_settings.theme_settings import (
			get_settings,
		)

		settings = get_settings()
	except Exception:
		return context

	css = ""

	if settings.get("apply_to_website") and settings.get("site_default_theme"):
		theme = frappe.db.get_value(
			"Theme Definition",
			settings["site_default_theme"],
			[*VAR_MAP, "is_dark"],
			as_dict=True,
		)
		if theme:
			css += theme_css_rules(theme)
			context.nexus_theme_is_dark = 1 if theme.get("is_dark") else 0

	favicon = settings.get("favicon")
	if favicon:
		context.favicon = favicon

	login_bg = settings.get("login_background")
	# The Nexus login page places this image in its own side panel, so the
	# blanket background rule below would double it up behind the form.
	on_nexus_login = bool(getattr(frappe.local, "flags", {}).get("nexus_login_page"))
	if login_bg and _is_login_route() and not on_nexus_login:
		# Only the login route; a background image behind every web page
		# would be a surprise, not a brand.
		safe = frappe.utils.escape_html(login_bg)
		css += (
			".page_content,.for-login,.login-content{"
			f"background-image:url('{safe}');"
			"background-size:cover;background-position:center;}"
		)

	if css:
		# Injected as `colocated_css`, NOT `head_include`.
		#
		# head_include is the obvious slot and works on ordinary web pages,
		# but frappe/www/login.html overrides that Jinja block to load
		# login.bundle.css and never calls {{ super() }} — so on the login
		# page, the one that matters most here, the variable was set on the
		# context and then silently discarded by the template.
		#
		# base.html renders `{% block style %}<style>{{ colocated_css }}</style>`
		# and no template in Frappe, ERPNext or this app overrides that block.
		# It is also populated in load_colocated_files(), which runs before
		# this hook, so appending cannot clobber a page's own CSS.
		context.colocated_css = (context.get("colocated_css") or "") + css

	return context


def _is_login_route() -> bool:
	path = (getattr(frappe.local, "path", "") or "").strip("/")
	return path in ("login", "update-password")
