from frappe.model.document import Document


class UserSoundPreference(Document):
	def validate(self):
		# Clamp volume to [0, 1] on every row so the client can always trust it.
		for row in self.sounds or []:
			if row.volume is None:
				row.volume = 0.5
			else:
				row.volume = max(0.0, min(1.0, float(row.volume)))
