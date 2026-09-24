import json

import frappe
from frappe import _
from frappe.model.document import Document

from nexus_theme.preferences import assert_own_row, own_row_permission, repair_owner


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
		# opt-out row above legitimately has none. Enforce it here instead.
		if not self.active_theme:
			frappe.throw(_("Pick a theme, or tick Use Frappe's Built-in Theme."))

		if self.overrides_json:
			try:
				parsed = json.loads(self.overrides_json)
			except TypeError, ValueError:
				frappe.throw(_("Overrides must be valid JSON."))
			if not isinstance(parsed, dict):
				frappe.throw(_("Overrides JSON must be an object."))
			# overrides_json is injected into the Desk as CSS on every boot.
			# set_active_theme() sanitizes what it is given, but this row can
			# also arrive through /api/resource or the form, so the guard has
			# to live here, on the row itself, to mean anything.
			from nexus_theme.utils.css_safety import sanitize_overrides

			self.overrides_json = json.dumps(sanitize_overrides(parsed))
		else:
			self.overrides_json = "{}"
