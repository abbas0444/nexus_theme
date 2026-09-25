"""Unit tests for reading a mini-rail (collapsed sidebar) value.

Pure-logic tests — no database or Frappe site required.
"""

import unittest

from nexus_theme.utils.rail import parse_collapsed


class TestParseCollapsed(unittest.TestCase):
	def test_every_honest_yes_is_collapsed(self):
		for given in (True, 1, "1", "true", "True", " TRUE ", "yes", "on", "collapsed"):
			self.assertIs(parse_collapsed(given), True, repr(given))

	def test_every_honest_no_is_expanded(self):
		for given in (False, 0, "0", "false", "False", "no", "off", "expanded", "", "  "):
			self.assertIs(parse_collapsed(given), False, repr(given))

	def test_nothing_at_all_means_expanded(self):
		"""An omitted argument is the sidebar's natural state, not an error."""
		self.assertIs(parse_collapsed(None), False)

	def test_anything_else_is_refused_rather_than_guessed(self):
		for bad in (2, -1, "2", "maybe", "collapse;", 1.0, [], {}, "1 OR 1=1"):
			self.assertIsNone(parse_collapsed(bad), repr(bad))


if __name__ == "__main__":
	unittest.main()
