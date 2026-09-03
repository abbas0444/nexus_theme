"""Site-wide governance and branding for themes and sounds.

Everything here is optional. A site that never opens this page behaves
exactly as it did before the DocType existed: custom themes allowed,
sharing allowed, no restriction list, no site default. That is deliberate —
the settings layer must not change behaviour until an admin opts in.
"""

import frappe
from frappe import _
from frappe.model.document import Document

CACHE_KEY = "nexus_theme_settings"

# The shape returned when Theme Settings has never been saved, or cannot be
# read (e.g. code deployed but `bench migrate` not run yet). Permissive by
# design, so a missing DocType can never lock users out of their own themes.
DEFAULTS = {
	"site_default_theme": None,
	"apply_to_website": 0,
	"allow_custom_themes": 1,
	"allow_public_sharing": 1,
	"restrict_theme_choice": 0,
	"allowed_themes": [],
	"allow_user_sounds": 1,
	"navbar_logo": None,
	"favicon": None,
	"login_background": None,
}


class ThemeSettings(Document):
	def validate(self):
		if self.restrict_theme_choice and not self.allowed_themes:
			frappe.throw(
				_("Add at least one theme to Allowed Themes, or turn off Restrict Theme Choice.")
			)
		if (
			self.restrict_theme_choice
			and self.site_default_theme
			and self.site_default_theme not in [r.theme for r in self.allowed_themes]
		):
			frappe.throw(_("The site default theme must be one of the allowed themes."))

	def on_update(self):
		clear_settings_cache()


def clear_settings_cache() -> None:
	try:
		frappe.cache.delete_value(CACHE_KEY)
	except Exception:
		try:
			frappe.cache().delete_value(CACHE_KEY)
		except Exception:
			pass
	# Theme choices ride along in every user's bootinfo.
	frappe.clear_cache()


def get_settings() -> dict:
	"""Return the effective settings as a plain dict, never raising.

	Cached because this is consulted on every boot_session and on every
	theme read. Any failure falls back to DEFAULTS rather than propagating:
	a governance layer that breaks the Desk when it is misconfigured is
	worse than no governance layer.
	"""

	def _load():
		doc = frappe.get_cached_doc("Theme Settings")
		data = {k: doc.get(k) for k in DEFAULTS if k != "allowed_themes"}
		data["allowed_themes"] = [r.theme for r in (doc.allowed_themes or []) if r.theme]
		return data

	try:
		cached = frappe.cache.get_value(CACHE_KEY, _load)
	except Exception:
		try:
			cached = _load()
		except Exception:
			return dict(DEFAULTS)

	if not isinstance(cached, dict):
		return dict(DEFAULTS)

	merged = dict(DEFAULTS)
	merged.update({k: v for k, v in cached.items() if k in DEFAULTS})
	return merged
