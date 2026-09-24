import frappe
from frappe.tests.utils import FrappeTestCase


class TestUserSoundPreference(FrappeTestCase):
	def test_volume_above_one_is_clamped(self):
		doc = frappe.new_doc("User Sound Preference")
		doc.append("sounds", {"event_key": "save", "file": "/files/x.mp3", "volume": 5})
		doc.validate()
		self.assertEqual(doc.sounds[0].volume, 1.0)

	def test_negative_volume_is_clamped(self):
		doc = frappe.new_doc("User Sound Preference")
		doc.append("sounds", {"event_key": "submit", "file": "/files/y.mp3", "volume": -2})
		doc.validate()
		self.assertEqual(doc.sounds[0].volume, 0.0)

	def test_missing_volume_defaults_to_half(self):
		doc = frappe.new_doc("User Sound Preference")
		doc.append("sounds", {"event_key": "alert", "file": "/files/z.mp3", "volume": None})
		doc.validate()
		self.assertEqual(doc.sounds[0].volume, 0.5)

	def test_a_file_off_this_site_is_refused_on_the_row(self):
		# set_user_sound() checks its argument, but the row's Attach field
		# accepts any string through /api/resource, and every file becomes an
		# <audio src> in the user's Desk.
		for bad in ("https://example.com/x.mp3", "javascript:alert(1)", "/files/x.exe"):
			with self.subTest(url=bad):
				doc = frappe.new_doc("User Sound Preference")
				doc.append("sounds", {"event_key": "save", "file": bad, "volume": 0.5})
				self.assertRaises(frappe.ValidationError, doc.validate)

	def test_in_range_volume_is_preserved(self):
		doc = frappe.new_doc("User Sound Preference")
		doc.append("sounds", {"event_key": "error", "file": "/files/e.mp3", "volume": 0.7})
		doc.validate()
		self.assertEqual(doc.sounds[0].volume, 0.7)
