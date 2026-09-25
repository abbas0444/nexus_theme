import re

import frappe
from frappe import _
from frappe.model.document import Document

from nexus_theme.preferences import is_privileged
from nexus_theme.utils.contrast import contrast_ratio, passes_aa
from nexus_theme.utils.css_safety import COLOR_FIELDS, STYLE_FIELDS, is_safe_value
from nexus_theme.utils.sidebar_skin import SIDEBAR_STYLES, sidebar_contrast_failures

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _settings() -> dict:
	from nexus_theme.nexus_theme.doctype.theme_settings.theme_settings import get_settings

	return get_settings()


class ThemeDefinition(Document):
	def validate(self):
		self._validate_ownership()
		self._validate_theme_key()
		self._validate_style_fields()
		self._validate_contrast()
		self._validate_sidebar_contrast()

	def _validate_ownership(self):
		"""What a Theme User may claim on a theme.

		save_custom_theme() sets these fields itself, but the DocType is also
		reachable through /api/resource and the form, where a Theme User could
		post `is_default: 1` (a bundled theme: shown to everyone, undeletable,
		exempt from the ownership checks), name someone else as `owner_user`,
		or share a theme on a site whose admin has turned sharing off. The
		rules are the API's, enforced on the row so every route obeys them.
		System Managers, and server-side code writing with ignore_permissions
		(install, patches, fixtures), are left alone.
		"""
		if self.flags.ignore_permissions or is_privileged():
			return

		if self.is_default:
			frappe.throw(_("Only a System Manager can mark a theme as a default theme."))

		settings = _settings()
		if not settings["allow_custom_themes"]:
			frappe.throw(_("Custom themes are disabled on this site."))

		# A theme you save is yours. Set rather than checked: the form leaves
		# the field empty, and the API fills it in the same way.
		self.owner_user = frappe.session.user

		if self.is_public and not settings["allow_public_sharing"]:
			# The API quietly drops the share flag too, so the theme still saves.
			self.is_public = 0

	def _validate_style_fields(self):
		"""Reject any color/style value that is not a plain color or CSS token.

		These fields are injected verbatim into other users' Desk as CSS — a
		Theme Definition can be shared via `is_public` — so an arbitrary string
		here is a stored cross-user CSS-injection vector. Runs before the
		contrast check so the latter only ever sees real hex colors."""
		for field in (*COLOR_FIELDS, *STYLE_FIELDS):
			value = self.get(field)
			if value in (None, ""):
				continue
			if not is_safe_value(field, value):
				label = self.meta.get_label(field) or field
				if field in COLOR_FIELDS:
					hint = _("must be a hex color such as #1a2b3c")
				elif field == "sidebar_style":
					hint = _("must be one of {0}").format(", ".join(SIDEBAR_STYLES))
				else:
					hint = _("contains characters that are not allowed")
				frappe.throw(_("{0} {1}.").format(_(label), hint))

	def on_update(self):
		self._clear_caches()

	def on_trash(self):
		if self.is_default:
			frappe.throw(_("Default themes cannot be deleted."))
		self._clear_caches()

	def _clear_caches(self):
		"""Drop every cache that holds this theme's values.

		Theme Settings clears everything when the site default changes, but
		editing the default theme itself cleared nothing: with "Apply to
		Login & Website" on, public pages are cached for half an hour with
		the old CSS baked in, and every user without a preference of their
		own kept the old palette in bootinfo. A shared theme has the same
		problem for everyone who applied it.
		"""
		from frappe.website.utils import clear_website_cache

		from nexus_theme.api import _invalidate_bootinfo

		if self.name == _settings()["site_default_theme"]:
			# The site default reaches everyone with no preference, and the
			# website. frappe.clear_cache() is what Theme Settings does for
			# the same reason; the website cache is named as well so the
			# intent survives if that ever narrows.
			frappe.clear_cache()
			clear_website_cache()
			return

		users = frappe.get_all(
			"User Theme Preference",
			or_filters={"active_theme": self.name, "dark_theme": self.name},
			pluck="user",
		)
		for user in set(users):
			_invalidate_bootinfo(user)

	def _validate_theme_key(self):
		if not self.theme_key:
			return
		if not _SLUG_RE.match(self.theme_key):
			frappe.throw(
				_(
					"Theme Key must be lowercase letters, digits and hyphens, and start "
					"with a letter or digit."
				)
			)

	def _validate_contrast(self):
		pairs = [
			("text_primary", "bg_primary", False),
			("text_primary", "bg_surface", False),
			# Buttons render with bold/larger UI chrome — AA Large (3:1) is the
			# correct WCAG threshold for button surfaces.
			("button_text", "button_bg", True),
		]
		for fg_field, bg_field, large in pairs:
			fg = self.get(fg_field)
			bg = self.get(bg_field)
			if not (fg and bg):
				continue
			try:
				ratio = contrast_ratio(fg, bg)
			except ValueError:
				continue
			if not passes_aa(fg, bg, large):
				# Report the threshold this pair was actually judged against —
				# button surfaces use AA Large (3:1), everything else AA (4.5:1).
				minimum = "3.0:1" if large else "4.5:1"
				msg = _("{0} on {1}: contrast ratio is {2} (WCAG minimum is {3}).").format(
					fg_field, bg_field, f"{ratio:.2f}", minimum
				)
				if self.is_default:
					frappe.throw(msg)
				else:
					frappe.msgprint(msg, indicator="orange", title=_("Low Contrast"))

	def _validate_sidebar_contrast(self):
		"""The sidebar text has to read on the sidebar it is painted on.

		Judged on the effective colours — an empty sidebar colour is derived
		from the accent, and an empty text colour picked for contrast — on
		every surface the text sits on: the sidebar, the far end of a
		gradient, and the active item. Plain is Frappe's own sidebar and is
		covered by the checks above. Same severity as those: a shipped theme
		must pass, a custom one is warned.
		"""
		for surface, ratio in sidebar_contrast_failures(self.as_dict()):
			msg = _("sidebar_text on {0}: contrast ratio is {1} (WCAG minimum is {2}).").format(
				surface, f"{ratio:.2f}", "4.5:1"
			)
			if self.is_default:
				frappe.throw(msg)
			else:
				frappe.msgprint(msg, indicator="orange", title=_("Low Contrast"))


# ---------------------------------------------------------------------------
# Permission hooks (see hooks.py)
# ---------------------------------------------------------------------------
#
# The Theme User role reads Theme Definition without `if_owner`, which is
# what lets the gallery show bundled and shared themes — and also what let
# every private theme on the site be read back through /api/resource. These
# two hooks narrow reads to the gallery's own rule: bundled, shared, or yours.
# frappe.get_all() ignores permissions, so get_available_themes() and the
# db.get_value() lookups behind get_active_theme() are unaffected.


def get_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	"""The WHERE clause a Theme User's list queries get."""
	user = user or frappe.session.user
	if is_privileged(user):
		return ""
	return (
		"(`tabTheme Definition`.`is_default` = 1"
		" or `tabTheme Definition`.`is_public` = 1"
		f" or `tabTheme Definition`.`owner_user` = {frappe.db.escape(user)})"
	)


def has_permission(doc, ptype: str | None = None, user: str | None = None, debug: bool = False) -> bool:
	"""The same rule, for a single document.

	A new document has no owner yet — validate() assigns one — so creation
	is left to the role permissions; a hook can only ever deny.
	"""
	user = user or frappe.session.user
	if is_privileged(user) or ptype == "create" or doc.is_new():
		return True
	return bool(doc.is_default or doc.is_public or doc.owner_user == user)
