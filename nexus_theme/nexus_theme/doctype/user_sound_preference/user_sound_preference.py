from frappe.model.document import Document

from nexus_theme.preferences import (
	assert_own_row,
	own_row_permission,
	repair_owner,
	repair_owner_after_save,
)


class UserSoundPreference(Document):
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

	def on_update(self):
		# The existing-row case of repair_owner: see preferences.py.
		repair_owner_after_save(self)

		# Every file becomes an <audio src> in this user's Desk. set_user_sound()
		# checks what it is handed, but a row can also arrive through
		# /api/resource or the form with any string in the Attach field, so the
		# same check has to run on the row itself. Imported here, not at the
		# top: api.py reaches this DocType through frappe.get_doc, and a
		# controller that imported api.py while being imported would go round
		# in a circle the moment api.py grew a module-level import of its own.
		from nexus_theme.api import _assert_sound_url

		# Clamp volume to [0, 1] on every row so the client can always trust it.
		for row in self.sounds or []:
			if row.file:
				_assert_sound_url(row.file)
			if row.volume is None:
				row.volume = 0.5
			else:
				row.volume = max(0.0, min(1.0, float(row.volume)))
