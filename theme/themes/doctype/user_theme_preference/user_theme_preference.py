import json

import frappe
from frappe import _
from frappe.model.document import Document


class UserThemePreference(Document):
	def validate(self):
		if self.overrides_json:
			try:
				parsed = json.loads(self.overrides_json)
			except (TypeError, ValueError):
				frappe.throw(_("Overrides must be valid JSON."))
			if not isinstance(parsed, dict):
				frappe.throw(_("Overrides JSON must be an object."))
		else:
			self.overrides_json = "{}"
