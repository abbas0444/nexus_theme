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
	# Login page. Off means Frappe's own sign-in screen, untouched.
	"use_nexus_login": 0,
	"login_brand_name": None,
	"login_brand_logo": None,
	"login_subtitle": None,
	"login_footnote": None,
	"login_headline": None,
	"login_subheadline": None,
	"login_points": None,
	"login_stat": None,
	"login_stat_note": None,
}


# Images shown to visitors who are not signed in: the favicon and login
# background on every public page, the brand logo on the Nexus login page,
# and the navbar logo, which that page falls back to.
PUBLIC_IMAGE_FIELDS = ("favicon", "navbar_logo", "login_background", "login_brand_logo")


class ThemeSettings(Document):
	def validate(self):
		if self.restrict_theme_choice and not self.allowed_themes:
			frappe.throw(_("Add at least one theme to Allowed Themes, or turn off Restrict Theme Choice."))
		if (
			self.restrict_theme_choice
			and self.site_default_theme
			and self.site_default_theme not in [r.theme for r in self.allowed_themes]
		):
			frappe.throw(_("The site default theme must be one of the allowed themes."))
		self._warn_about_private_images()

	def _warn_about_private_images(self):
		"""Say so when a brand image is a private upload.

		The upload dialog defaults to private, and a private file answers
		403 to anyone not signed in — so the favicon and login images are
		silently skipped for visitors (see login_page.public_file). A warning
		rather than an error: the setting is still valid for the Desk, and
		the admin may be halfway through swapping the files.
		"""
		private = [
			_(self.meta.get_label(field))
			for field in PUBLIC_IMAGE_FIELDS
			if (self.get(field) or "").strip().startswith("/private/")
		]
		if private:
			frappe.msgprint(
				_(
					"{0}: private files are not shown to visitors who are not signed in, "
					"so they will be left off the login page and website. Upload them as public files."
				).format(", ".join(private)),
				indicator="orange",
				title=_("Private Images"),
			)

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
