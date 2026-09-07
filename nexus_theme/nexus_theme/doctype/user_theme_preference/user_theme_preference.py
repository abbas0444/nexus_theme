import json

import frappe
from frappe import _
from frappe.model.document import Document


class UserThemePreference(Document):
	def validate(self):
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
		else:
			self.overrides_json = "{}"
