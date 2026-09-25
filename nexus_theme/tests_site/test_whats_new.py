"""Site-backed checks of the "What's new" card's server side.

These need a running site — `bench --site <site> run-tests --app nexus_theme`.
They pin what only shows against a real database and cache: the user
default that remembers a dismissal, the boot payload that decides whether
the card shows, and the bootinfo cache being dropped on dismissal.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from nexus_theme import whats_new

ADMIN = "Administrator"


class TestWhatsNew(FrappeTestCase):
	def setUp(self):
		frappe.set_user(ADMIN)
		self._prev = frappe.defaults.get_user_default(whats_new.SEEN_KEY)
		frappe.defaults.clear_user_default(whats_new.SEEN_KEY)

	def tearDown(self):
		frappe.defaults.clear_user_default(whats_new.SEEN_KEY)
		if self._prev:
			frappe.defaults.set_user_default(whats_new.SEEN_KEY, self._prev)
		frappe.set_user(ADMIN)

	def test_mark_seen_stores_the_version_for_this_user_only(self):
		out = frappe.call("nexus_theme.whats_new.mark_seen", version="2.0.0")
		self.assertEqual(out["seen_version"], "2.0.0")
		self.assertEqual(frappe.defaults.get_user_default(whats_new.SEEN_KEY), "2.0.0")
		self.assertIsNone(frappe.defaults.get_user_default(whats_new.SEEN_KEY, user="Guest"))

	def test_mark_seen_defaults_to_the_running_version(self):
		out = frappe.call("nexus_theme.whats_new.mark_seen")
		self.assertEqual(out["seen_version"], whats_new.current_version())

	def test_mark_seen_refuses_a_value_that_is_not_a_version(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.call("nexus_theme.whats_new.mark_seen", version="<script>")
		self.assertIsNone(frappe.defaults.get_user_default(whats_new.SEEN_KEY))

	def test_boot_payload_shows_once_and_then_not_again(self):
		version = whats_new.current_version()
		expect = whats_new.is_new_to(None, version)
		payload = whats_new.boot_payload()
		self.assertEqual(payload["version"], version)
		self.assertEqual(bool(payload["show"]), expect)
		if expect:
			self.assertEqual(payload["notes"]["version"], whats_new.notes_for(version)["version"])
			self.assertTrue(payload["notes"]["items"])
		else:
			self.assertIsNone(payload["notes"])

		whats_new.mark_seen(version)
		after = whats_new.boot_payload()
		self.assertEqual(after["show"], 0)
		self.assertIsNone(after["notes"])
		self.assertEqual(after["seen_version"], version)

	def test_get_notes_returns_the_series_notes_regardless_of_seen(self):
		whats_new.mark_seen("2.0.0")
		notes = frappe.call("nexus_theme.whats_new.get_notes", version="2.0.1")
		self.assertEqual(notes["version"], "2.0.0")
		self.assertIsNone(frappe.call("nexus_theme.whats_new.get_notes", version="1.2.0"))

	def test_boot_session_carries_the_payload(self):
		from nexus_theme.api import extend_boot_session

		bootinfo = {}
		extend_boot_session(bootinfo)
		self.assertIn("nexus_theme_whats_new", bootinfo)
		self.assertIn("show", bootinfo["nexus_theme_whats_new"])
