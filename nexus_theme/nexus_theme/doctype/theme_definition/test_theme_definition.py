import frappe
from frappe.tests.utils import FrappeTestCase

from nexus_theme.nexus_theme.doctype.theme_definition.theme_definition import _SLUG_RE
from nexus_theme.nexus_theme.doctype.theme_settings.theme_settings import clear_settings_cache

ADMIN = "Administrator"
THEME_USER = "nxt-theme-owner@example.com"
OTHER_USER = "nxt-theme-other@example.com"


def _theme_user(email: str):
	"""A Desk user holding only Theme User."""
	if frappe.db.exists("User", email):
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)
	return frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": "Theme Test",
			"send_welcome_email": 0,
			"roles": [{"role": "Theme User"}],
		}
	).insert(ignore_permissions=True)


def _bundled() -> str | None:
	return frappe.db.get_value("Theme Definition", {"is_default": 1}, "name")


class TestThemeDefinition(FrappeTestCase):
	def setUp(self):
		frappe.set_user(ADMIN)
		self._made: list[str] = []

	def tearDown(self):
		frappe.set_user(ADMIN)
		# Settings first: a theme made here may be the site default.
		self._govern(allow_custom=1, allow_sharing=1, site_default=None)
		for name in self._made:
			if frappe.db.exists("Theme Definition", name):
				frappe.db.delete("User Theme Preference", {"active_theme": name})
				frappe.delete_doc("Theme Definition", name, force=True, ignore_permissions=True)
		for email in (THEME_USER, OTHER_USER):
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, force=True, ignore_permissions=True)

	def _govern(self, allow_custom, allow_sharing, site_default):
		doc = frappe.get_single("Theme Settings")
		doc.allow_custom_themes = allow_custom
		doc.allow_public_sharing = allow_sharing
		doc.site_default_theme = site_default
		doc.flags.ignore_permissions = True
		doc.save()
		clear_settings_cache()

	def _custom(self, key: str, **values):
		"""A custom theme copied from a bundled one, saved as the session user."""
		base = _bundled()
		if not base:
			self.skipTest("no bundled theme on this site")
		doc = frappe.copy_doc(frappe.get_doc("Theme Definition", base))
		doc.theme_key = key
		doc.theme_name = key.replace("-", " ").title()
		doc.is_default = 0
		doc.is_public = 0
		doc.owner_user = None
		for k, v in values.items():
			setattr(doc, k, v)
		self._made.append(key)
		return doc

	def test_slug_regex_accepts_valid_keys(self):
		for key in ("indigo", "midnight-indigo", "theme1", "a-b-c"):
			self.assertRegex(key, _SLUG_RE)

	def test_slug_regex_rejects_invalid_keys(self):
		for key in ("Indigo", "midnight_indigo", "-leading", "with space", ""):
			self.assertIsNone(_SLUG_RE.match(key))

	def test_invalid_theme_key_is_rejected(self):
		doc = frappe.get_doc(
			{
				"doctype": "Theme Definition",
				"theme_name": "FAS Test Bad Key",
				"theme_key": "Bad_Key",
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_low_contrast_default_theme_is_blocked(self):
		# Default themes must pass WCAG AA — a grey-on-grey theme is rejected.
		doc = frappe.get_doc(
			{
				"doctype": "Theme Definition",
				"theme_name": "FAS Test Low Contrast",
				"theme_key": "nxt-test-low-contrast",
				"is_default": 1,
				"text_primary": "#777777",
				"bg_primary": "#888888",
				"bg_surface": "#888888",
				"button_text": "#777777",
				"button_bg": "#888888",
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	# ------------------------------------------------------------------
	# What a Theme User may claim on a theme
	# ------------------------------------------------------------------

	def test_a_theme_user_cannot_mark_a_theme_as_default(self):
		_theme_user(THEME_USER)
		frappe.set_user(THEME_USER)
		doc = self._custom("nxt-test-not-default", is_default=1)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_a_theme_user_owns_what_they_save(self):
		_theme_user(THEME_USER)
		_theme_user(OTHER_USER)
		frappe.set_user(THEME_USER)
		doc = self._custom("nxt-test-owned", owner_user=OTHER_USER)
		doc.insert()
		self.assertEqual(doc.owner_user, THEME_USER)

	def test_a_system_manager_may_name_any_owner(self):
		_theme_user(OTHER_USER)
		doc = self._custom("nxt-test-admin-owned", owner_user=OTHER_USER)
		doc.insert()
		self.assertEqual(doc.owner_user, OTHER_USER)

	def test_sharing_follows_the_site_switch(self):
		_theme_user(THEME_USER)
		self._govern(allow_custom=1, allow_sharing=0, site_default=None)
		frappe.set_user(THEME_USER)
		doc = self._custom("nxt-test-not-shared", is_public=1)
		doc.insert()
		self.assertEqual(doc.is_public, 0)

	def test_custom_themes_off_blocks_the_row_too(self):
		_theme_user(THEME_USER)
		self._govern(allow_custom=0, allow_sharing=1, site_default=None)
		frappe.set_user(THEME_USER)
		doc = self._custom("nxt-test-no-custom")
		self.assertRaises(frappe.ValidationError, doc.insert)

	# ------------------------------------------------------------------
	# Who may read a theme
	# ------------------------------------------------------------------

	def test_a_private_theme_is_read_only_by_its_owner(self):
		_theme_user(THEME_USER)
		_theme_user(OTHER_USER)
		frappe.set_user(THEME_USER)
		private = self._custom("nxt-test-private")
		private.insert()
		shared = self._custom("nxt-test-shared", is_public=1)
		shared.insert()

		frappe.set_user(OTHER_USER)
		listed = set(frappe.get_list("Theme Definition", pluck="name", limit=0))
		self.assertNotIn(private.name, listed)
		self.assertIn(shared.name, listed)
		self.assertIn(_bundled(), listed)
		self.assertFalse(frappe.has_permission("Theme Definition", "read", doc=private.name))
		self.assertTrue(frappe.has_permission("Theme Definition", "read", doc=shared.name))
		self.assertTrue(frappe.has_permission("Theme Definition", "read", doc=_bundled()))

		frappe.set_user(THEME_USER)
		self.assertIn(private.name, set(frappe.get_list("Theme Definition", pluck="name", limit=0)))
		self.assertTrue(frappe.has_permission("Theme Definition", "read", doc=private.name))

	# ------------------------------------------------------------------
	# Names
	# ------------------------------------------------------------------

	def test_two_users_may_give_their_themes_the_same_name(self):
		"""theme_key is the docname; theme_name is only a label. It used to
		be unique across the site, so the second person to call their theme
		"My Theme" — or anyone naming theirs after a bundled one — got a raw
		duplicate-entry error."""
		_theme_user(THEME_USER)
		_theme_user(OTHER_USER)
		frappe.set_user(THEME_USER)
		self._custom("nxt-test-same-name-a", theme_name="Dracula").insert()
		frappe.set_user(OTHER_USER)
		self._custom("nxt-test-same-name-b", theme_name="Dracula").insert()  # used to raise here
		self.assertEqual(
			frappe.db.count("Theme Definition", {"theme_name": "Dracula", "is_default": 0}),
			2,
		)

	def test_default_theme_cannot_be_deleted(self):
		default = frappe.get_all("Theme Definition", filters={"is_default": 1}, limit=1)
		if not default:
			self.skipTest("no default themes present in this site")
		self.assertRaises(
			frappe.ValidationError,
			frappe.delete_doc,
			"Theme Definition",
			default[0].name,
		)
