import re
import frappe
from frappe import _
from frappe.model.document import Document

from theme.utils.contrast import contrast_ratio, passes_aa

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ThemeDefinition(Document):
	def validate(self):
		self._validate_theme_key()
		self._validate_contrast()

	def on_trash(self):
		if self.is_default:
			frappe.throw(_("Default themes cannot be deleted."))

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
				msg = _(
					"{0} on {1}: contrast ratio is {2} (WCAG AA minimum is 4.5:1)."
				).format(fg_field, bg_field, f"{ratio:.2f}")
				if self.is_default:
					frappe.throw(msg)
				else:
					frappe.msgprint(msg, indicator="orange", title=_("Low Contrast"))
