import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from nexus_theme.preferences import (
	assert_own_row,
	own_row_permission,
	repair_owner,
	repair_owner_after_save,
)
from nexus_theme.utils.density import label_for, normalize_density


class UserThemePreference(Document):
	def has_permission(self, permtype="read", *, debug=False, user=None) -> bool:
		# The row belongs to `user`, whoever inserted it. See preferences.py.
		if super().has_permission(permtype, debug=debug, user=user):
			return True
		return own_row_permission(self, permtype, user)

	def validate(self):
		# Before anything else: a row for someone else must never get as far
		# as being cleaned up and stored.
		assert_own_row(self)
		repair_owner(self)

		# Density is independent of the theme and is kept through every
		# branch below: opting out of our themes, or having none yet, says
		# nothing about how much room the person wants their rows to take.
		# Stored as the Select label; a key ("compact") from the API or a
		# stray case from the form is put into that shape here.
		if self.density:
			key = normalize_density(self.density)
			if not key:
				frappe.throw(
					_("{0} is not a density. Choose Compact, Comfortable or Spacious.").format(self.density)
				)
			self.density = label_for(key)
		else:
			self.density = None

		# The mini rail, likewise the person's and not the theme's. A Check,
		# so anything truthy from /api/resource is put back to 0 or 1.
		self.sidebar_collapsed = 1 if cint(self.get("sidebar_collapsed")) else 0

		if self.use_frappe_theme:
			# An explicit opt-out: the user picked Frappe's own theme over any
			# of ours, the site default included. Nothing of ours may stay on
			# the row, or get_active_theme() would have two answers.
			self.active_theme = None
			self.dark_theme = None
			self.theme_mode = "Single"
			self.overrides_json = "{}"
			return

		# `active_theme` is not marked required on the DocType because the
		# opt-out row above legitimately has none — and so does a row that
		# carries only a density or a collapsed sidebar: someone who picked
		# Compact, or folded the sidebar to a rail, before ever picking a
		# theme, or whose theme was deleted from under them. That row means
		# "no theme opinion" and reads exactly like having no row, site
		# default included, so nothing theme-shaped may linger on it. A row
		# with none of these is an empty row, and is refused as before.
		if not self.active_theme:
			if not self.density and not self.sidebar_collapsed:
				frappe.throw(_("Pick a theme, or tick Use Frappe's Built-in Theme."))
			self.dark_theme = None
			self.theme_mode = "Single"
			self.overrides_json = "{}"
			return

		if self.overrides_json:
			try:
				parsed = json.loads(self.overrides_json)
			except (TypeError, ValueError):
				frappe.throw(_("Overrides must be valid JSON."))
			if not isinstance(parsed, dict):
				frappe.throw(_("Overrides JSON must be an object."))
			# overrides_json is injected into the Desk as CSS on every boot.
			# set_active_theme() sanitizes what it is given, but this row can
			# also arrive through /api/resource or the form, so the guard has
			# to live here, on the row itself, to mean anything. The blob
			# form, so the dark half nested inside it survives the pass.
			from nexus_theme.utils.css_safety import sanitize_overrides_blob

			self.overrides_json = json.dumps(sanitize_overrides_blob(parsed))
		else:
			self.overrides_json = "{}"

	def on_update(self):
		# The existing-row case of repair_owner: see preferences.py.
		repair_owner_after_save(self)
