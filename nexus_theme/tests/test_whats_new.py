"""Unit tests for the release-notes logic behind the "What's new" card.

Pure-logic tests — series parsing and the seen/new decision need no site.
The parts that touch frappe (user defaults, the boot payload) are covered
in tests_site/test_whats_new.py.
"""

import unittest

from nexus_theme.whats_new import RELEASES, is_new_to, notes_for, series


class TestSeries(unittest.TestCase):
	def test_major_and_minor_only(self):
		self.assertEqual(series("2.0.0"), (2, 0))
		self.assertEqual(series("2.0.7"), (2, 0))
		self.assertEqual(series("2.1.0"), (2, 1))
		self.assertEqual(series("10.3"), (10, 3))

	def test_one_number_means_minor_zero(self):
		self.assertEqual(series("3"), (3, 0))

	def test_garbage_is_none(self):
		for bad in (None, "", " ", "x.y", "2.x.0", "beta"):
			self.assertIsNone(series(bad), bad)

	def test_whitespace_is_tolerated(self):
		self.assertEqual(series(" 2.0.0 "), (2, 0))


class TestNotes(unittest.TestCase):
	def test_every_release_has_the_shape_the_card_needs(self):
		for release in RELEASES:
			self.assertIsNotNone(series(release["version"]))
			self.assertTrue(release["title"])
			self.assertTrue(release["summary"])
			self.assertTrue(release["items"])
			for item in release["items"]:
				self.assertTrue(item["heading"])
				self.assertTrue(item["text"])
				if item.get("command"):
					self.assertTrue(item.get("command_label"))

	def test_notes_match_on_series_not_on_patch(self):
		self.assertEqual(notes_for("2.0.0")["version"], "2.0.0")
		self.assertEqual(notes_for("2.0.3")["version"], "2.0.0")

	def test_a_version_with_nothing_to_say_has_no_notes(self):
		self.assertIsNone(notes_for("1.2.0"))
		self.assertIsNone(notes_for("99.9.9"))
		self.assertIsNone(notes_for(""))


class TestIsNewTo(unittest.TestCase):
	def test_never_seen_anything(self):
		self.assertTrue(is_new_to(None, "2.0.0"))
		self.assertTrue(is_new_to("", "2.0.0"))

	def test_seen_an_older_series(self):
		self.assertTrue(is_new_to("1.2.0", "2.0.0"))
		self.assertTrue(is_new_to("1.9.9", "2.0.0"))

	def test_someone_who_saw_2_0_is_told_about_2_1(self):
		self.assertTrue(is_new_to("2.0.0", "2.1.0"))
		self.assertEqual(notes_for("2.1.4")["version"], "2.1.0")

	def test_seen_this_series_already(self):
		self.assertFalse(is_new_to("2.0.0", "2.0.0"))
		self.assertFalse(is_new_to("2.0.0", "2.0.4"))

	def test_seen_something_newer(self):
		# A downgrade, or a shared default: never nag.
		self.assertFalse(is_new_to("2.1.0", "2.0.0"))

	def test_quiet_when_the_running_version_has_no_notes(self):
		self.assertFalse(is_new_to(None, "1.2.0"))
		self.assertFalse(is_new_to("1.0.0", "1.2.0"))


if __name__ == "__main__":
	unittest.main()
