"""Unit tests for the Nexus Home page's pure rules.

Pure-logic tests — no database or Frappe site required. The site-backed
checks (permissions, to-do counts, the boot landing) are in
tests_site/test_home.py.
"""

import ast
import json
import re
import unittest
from pathlib import Path

from nexus_theme.utils.home import (
	DEFAULT_LAYOUT,
	HOME_PAGE,
	TINT_COUNT,
	build_tiles,
	counts_by_module,
	first_name_for,
	greeting_bucket,
	normalize_layout,
	tint_index,
)

APP = Path(__file__).resolve().parents[1]
PAGE_DIR = APP / "nexus_theme" / "page" / "nexus_home"


class TestGreeting(unittest.TestCase):
	def test_hours_fall_into_three_buckets(self):
		want = {
			0: "evening",
			4: "evening",
			5: "morning",
			11: "morning",
			12: "afternoon",
			17: "afternoon",
			18: "evening",
			23: "evening",
		}
		for hour, bucket in want.items():
			with self.subTest(hour=hour):
				self.assertEqual(greeting_bucket(hour), bucket)

	def test_every_hour_has_a_bucket_and_odd_input_does_not_raise(self):
		for hour in range(24):
			self.assertIn(greeting_bucket(hour), ("morning", "afternoon", "evening"))
		self.assertEqual(greeting_bucket(24), "evening")  # wraps to midnight
		self.assertEqual(greeting_bucket("9"), "morning")
		self.assertEqual(greeting_bucket(None), "morning")
		self.assertEqual(greeting_bucket("soon"), "morning")

	def test_the_page_script_uses_the_same_boundaries(self):
		js = (PAGE_DIR / "nexus_home.js").read_text()
		self.assertIn("h >= 5 && h < 12", js)
		self.assertIn("h >= 12 && h < 18", js)

	def test_first_name(self):
		self.assertEqual(first_name_for("Ayesha", "Ayesha Khan", "a@x.com"), "Ayesha")
		self.assertEqual(first_name_for(None, "  Ayesha Khan ", "a@x.com"), "Ayesha")
		self.assertEqual(first_name_for("", "", "ayesha@x.com"), "ayesha")
		self.assertEqual(first_name_for(None, None, "Administrator"), "Administrator")


class TestTints(unittest.TestCase):
	def test_tint_is_stable_and_in_range(self):
		for name in ("Selling", "Buying", "Accounts", "", "Ünïcødé ✓", "x" * 500):
			with self.subTest(name=name):
				first = tint_index(name)
				self.assertEqual(first, tint_index(name))
				self.assertGreaterEqual(first, 0)
				self.assertLess(first, TINT_COUNT)

	def test_known_values_pin_the_hash(self):
		# The page script repeats this hash for tiles built from boot; these
		# values pin it so a change on one side is noticed.
		self.assertEqual(tint_index(""), 0)
		self.assertEqual(tint_index("a"), 97 % TINT_COUNT)
		self.assertEqual(tint_index("ab"), (97 * 31 + 98) % TINT_COUNT)

	def test_names_spread_over_the_palette(self):
		names = [
			"Accounts",
			"Assets",
			"Buying",
			"CRM",
			"HR",
			"Manufacturing",
			"Projects",
			"Quality",
			"Selling",
			"Stock",
			"Support",
			"Website",
		]
		self.assertGreaterEqual(len({tint_index(n) for n in names}), 4)

	def test_css_and_script_define_the_same_number_of_tints(self):
		css = (PAGE_DIR / "nexus_home.css").read_text()
		light = set(re.findall(r"^\.nxh-tint-(\d+) \{", css, re.M))
		dark = set(re.findall(r'^html\[data-theme="dark"\] \.nxh-tint-(\d+) \{', css, re.M))
		want = {str(i) for i in range(TINT_COUNT)}
		self.assertEqual(light, want)
		self.assertEqual(dark, want)
		js = (PAGE_DIR / "nexus_home.js").read_text()
		self.assertIn(f"const TINTS = {TINT_COUNT};", js)


class TestLayout(unittest.TestCase):
	def test_labels_and_keys(self):
		self.assertEqual(normalize_layout("Grid"), "grid")
		self.assertEqual(normalize_layout("Compact list"), "list")
		self.assertEqual(normalize_layout("list"), "list")
		self.assertEqual(normalize_layout(" GRID "), "grid")

	def test_anything_else_is_the_grid(self):
		for value in (None, "", "Masonry", 0):
			self.assertEqual(normalize_layout(value), DEFAULT_LAYOUT)
		self.assertEqual(DEFAULT_LAYOUT, "grid")

	def test_settings_select_offers_every_layout(self):
		from nexus_theme.utils.home import LAYOUTS

		meta = json.loads(
			(APP / "nexus_theme" / "doctype" / "theme_settings" / "theme_settings.json").read_text()
		)
		field = next(f for f in meta["fields"] if f["fieldname"] == "home_layout")
		self.assertEqual(field["options"].split("\n"), list(LAYOUTS.values()))
		self.assertEqual(normalize_layout(field["default"]), DEFAULT_LAYOUT)


class TestCounts(unittest.TestCase):
	def test_todos_roll_up_to_modules(self):
		got = counts_by_module(
			{"Sales Order": 2, "Quotation": 1, "Purchase Order": 4, "Mystery": 3, "Note": 0},
			{
				"Sales Order": "Selling",
				"Quotation": "Selling",
				"Purchase Order": "Buying",
				"Note": "Desk",
			},
		)
		self.assertEqual(got, {"Selling": 3, "Buying": 4})

	def test_empty_inputs(self):
		self.assertEqual(counts_by_module({}, {}), {})
		self.assertEqual(counts_by_module(None, None), {})


class TestTiles(unittest.TestCase):
	PAGES = (
		{
			"name": "Selling",
			"title": "Selling",
			"label": "Selling",
			"public": 1,
			"module": "Selling",
			"icon": "sell",
		},
		{"name": "Buying", "title": "Buying", "public": 1, "module": "Buying"},
		{"name": "Hidden", "title": "Hidden", "public": 1, "is_hidden": 1},
		{"name": "Child", "title": "Child", "public": 1, "parent_page": "Selling"},
		{"name": "Mine-me@x.com", "title": "Mine", "public": 0, "for_user": "me@x.com"},
		{"name": "Theirs-you@x.com", "title": "Theirs", "public": 0, "for_user": "you@x.com"},
		{"name": "Selling", "title": "Selling again", "public": 1},
		{"name": "Docs", "title": "Docs", "public": 1, "type": "URL", "external_link": "https://example.com"},
		{
			"name": "Ledger",
			"title": "Ledger",
			"public": 1,
			"type": "Link",
			"link_type": "Report",
			"link_to": "General Ledger",
			"report": {"report_type": "Script Report", "ref_doctype": "GL Entry"},
		},
	)

	def test_only_top_level_visible_own_workspaces_become_tiles(self):
		tiles = build_tiles(self.PAGES, {"Selling": 5}, user="me@x.com")
		self.assertEqual([t["name"] for t in tiles], ["Selling", "Buying", "Mine-me@x.com", "Docs", "Ledger"])

	def test_tile_shape(self):
		tiles = {t["name"]: t for t in build_tiles(self.PAGES, {"Selling": 5}, user="me@x.com")}
		selling = tiles["Selling"]
		self.assertEqual(selling["count"], 5)
		self.assertEqual(selling["icon"], "sell")
		self.assertEqual(selling["public"], 1)
		self.assertEqual(selling["tint"], tint_index("Selling"))
		self.assertEqual(selling["type"], "Workspace")
		self.assertEqual(tiles["Buying"]["count"], 0)
		self.assertEqual(tiles["Buying"]["label"], "Buying")
		self.assertEqual(tiles["Mine-me@x.com"]["public"], 0)
		self.assertEqual(tiles["Mine-me@x.com"]["title"], "Mine")
		self.assertEqual(tiles["Docs"]["external_link"], "https://example.com")
		self.assertEqual(tiles["Ledger"]["link_to"], "General Ledger")
		self.assertEqual(tiles["Ledger"]["report"]["report_type"], "Script Report")

	def test_nothing_in_nothing_out(self):
		self.assertEqual(build_tiles(None), [])
		self.assertEqual(build_tiles([{}]), [])


class TestPageRecord(unittest.TestCase):
	def test_page_json_is_open_to_every_desk_user(self):
		page = json.loads((PAGE_DIR / "nexus_home.json").read_text())
		self.assertEqual(page["name"], HOME_PAGE)
		self.assertEqual(page["page_name"], HOME_PAGE)
		self.assertEqual(page["module"], "Nexus Theme")
		self.assertEqual(page["standard"], "Yes")
		# No roles = every signed-in user may open it, as with the studios.
		self.assertEqual(page["roles"], [])

	def test_settings_defaults_match_the_doctype(self):
		# Read DEFAULTS out of the controller's source: importing it would
		# pull in frappe, and these tests run without a site.
		source = (APP / "nexus_theme" / "doctype" / "theme_settings" / "theme_settings.py").read_text()
		tree = ast.parse(source)
		node = next(
			n
			for n in tree.body
			if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == "DEFAULTS" for t in n.targets)
		)
		DEFAULTS = ast.literal_eval(node.value)

		meta = json.loads(
			(APP / "nexus_theme" / "doctype" / "theme_settings" / "theme_settings.json").read_text()
		)
		fields = {f["fieldname"]: f for f in meta["fields"]}
		for key in ("use_nexus_home", "home_show_greeting", "home_show_shortcuts", "home_layout"):
			with self.subTest(field=key):
				self.assertIn(key, meta["field_order"])
				self.assertEqual(str(DEFAULTS[key]), fields[key]["default"])
		self.assertEqual(DEFAULTS["use_nexus_home"], 0)


if __name__ == "__main__":
	unittest.main()
