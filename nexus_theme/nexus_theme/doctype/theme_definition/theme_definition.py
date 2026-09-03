import re
import frappe
from frappe import _
from frappe.model.document import Document

from nexus_theme.utils.contrast import contrast_ratio, passes_aa
from nexus_theme.utils.css_safety import COLOR_FIELDS, STYLE_FIELDS, is_safe_value

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ThemeDefinition(Document):
	def validate(self):
		self._validate_theme_key()
		self._validate_style_fields()
		self._validate_contrast()

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
				else:
					hint = _("contains characters that are not allowed")
				frappe.throw(_("{0} {1}.").format(_(label), hint))

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
				# Report the threshold this pair was actually judged against —
				# button surfaces use AA Large (3:1), everything else AA (4.5:1).
				minimum = "3.0:1" if large else "4.5:1"
				msg = _(
					"{0} on {1}: contrast ratio is {2} (WCAG minimum is {3})."
				).format(fg_field, bg_field, f"{ratio:.2f}", minimum)
				if self.is_default:
					frappe.throw(msg)
				else:
					frappe.msgprint(msg, indicator="orange", title=_("Low Contrast"))
