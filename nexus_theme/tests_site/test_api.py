"""Site-backed checks of the whitelisted API.

These need a running site — `bench --site <site> run-tests --app nexus_theme`
— so they live outside nexus_theme/tests, which stays runnable with plain
unittest and no site at all. Each one pins a behaviour that only shows up
against a real database: link checks on delete, docname collisions,
role provisioning through User's own validate(), and the site switches.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from nexus_theme import api
from nexus_theme.install import THEME_USER_ROLE
from nexus_theme.nexus_theme.doctype.theme_settings.theme_settings import (
	clear_settings_cache,
)

ADMIN = "Administrator"
SOUND = "/assets/nexus_theme/sounds/save-2.wav"


def _bundled(is_dark: int) -> str | None:
	return frappe.db.get_value("Theme Definition", {"is_default": 1, "is_dark": is_dark}, "name")


def _portable(theme_name: str) -> dict:
	return api.export_theme(theme_name)["theme"]


class TestThemeApi(FrappeTestCase):
	def setUp(self):
		frappe.set_user(ADMIN)
		s = frappe.get_doc("Theme Settings")
		self._prev = (
			s.site_default_theme,
			s.restrict_theme_choice,
			[r.theme for r in (s.allowed_themes or [])],
			s.allow_user_sounds,
		)
		self._govern(None, 0, [], 1)
		self._drop_pref(ADMIN)
		self._made: list[str] = []

	def tearDown(self):
		frappe.set_user(ADMIN)
		self._drop_pref(ADMIN)
		api.clear_all_user_sounds()
		self._govern(*self._prev)
		for name in self._made:
			if frappe.db.exists("Theme Definition", name):
				frappe.db.delete("User Theme Preference", {"active_theme": name})
				frappe.delete_doc("Theme Definition", name, force=True, ignore_permissions=True)

	def _govern(self, site_default, restrict, allowed, sounds):
		doc = frappe.get_doc("Theme Settings")
		doc.site_default_theme = site_default
		doc.restrict_theme_choice = restrict
		doc.set("allowed_themes", [{"theme": t} for t in allowed])
		doc.allow_user_sounds = sounds
		doc.save(ignore_permissions=True)
		clear_settings_cache()

	def _drop_pref(self, user):
		name = frappe.db.exists("User Theme Preference", {"user": user})
		if name:
			frappe.delete_doc("User Theme Preference", name, force=True, ignore_permissions=True)

	def _save_custom(self, key: str, base: str | None = None) -> str:
		payload = dict(
			_portable(base or _bundled(0)),
			theme_key=key,
			theme_name=key.replace("-", " ").title(),
		)
		name = api.save_custom_theme(payload, share_public=0)["name"]
		self._made.append(name)
		return name

	# ------------------------------------------------------------------
	# Deleting
	# ------------------------------------------------------------------

	def test_deleting_the_theme_in_use_releases_it_first(self):
		name = self._save_custom("nxt-test-in-use")
		api.set_active_theme(name)
		self.assertEqual(api.get_active_theme()["theme"]["name"], name)

		api.delete_custom_theme(name)  # used to raise LinkExistsError here

		self.assertFalse(frappe.db.exists("Theme Definition", name))
		self.assertFalse(frappe.db.exists("User Theme Preference", {"user": ADMIN}))
		self.assertIsNone(api.get_active_theme()["theme"])  # back to never-chose

	def test_deleting_the_dark_half_of_a_pair_drops_to_single(self):
		light, dark_base = _bundled(0), _bundled(1)
		if not (light and dark_base):
			self.skipTest("need one bundled light and one dark theme")
		dark = self._save_custom("nxt-test-dark-half", base=dark_base)
		api.set_active_theme(light)
		api.set_theme_mode("Automatic", dark_theme=dark)
		self.assertEqual(api.get_active_theme()["mode"], "Automatic")

		api.delete_custom_theme(dark)

		got = api.get_active_theme()
		self.assertEqual(got["mode"], "Single")
		self.assertEqual(got["theme"]["name"], light)

	def test_turning_pairing_off_works_without_a_theme(self):
		"""Someone on Frappe's own look must still be able to leave Automatic.

		The guard that stops you *enabling* pairing without a theme used to run
		for both modes, so "Single" answered "Pick a theme before enabling
		automatic switching" — advice for the opposite of what was asked, and a
		dead end in the Auto Light/Dark dialog.
		"""
		light, dark_base = _bundled(0), _bundled(1)
		if not (light and dark_base):
			self.skipTest("need one bundled light and one dark theme")

		api.set_active_theme(light)
		api.set_theme_mode("Automatic", dark_theme=dark_base)
		self.assertEqual(api.get_active_theme()["mode"], "Automatic")

		api.clear_active_theme()  # "use Frappe's own look"
		api.set_theme_mode("Single")  # must not raise

		self.assertEqual(api.get_active_theme()["mode"], "Single")

	def test_pairing_still_needs_a_theme_to_pair_with(self):
		dark_base = _bundled(1)
		if not dark_base:
			self.skipTest("need one bundled dark theme")
		api.clear_active_theme()
		self.assertRaises(frappe.ValidationError, api.set_theme_mode, "Automatic", dark_theme=dark_base)

	def test_single_is_a_no_op_when_nothing_is_stored(self):
		"""A brand-new user has no preference row at all."""
		if frappe.db.exists("User Theme Preference", {"user": ADMIN}):
			frappe.delete_doc(
				"User Theme Preference",
				frappe.db.get_value("User Theme Preference", {"user": ADMIN}),
				force=True,
				ignore_permissions=True,
			)
		self.assertEqual(api.set_theme_mode("Single")["mode"], "Single")
		self.assertFalse(frappe.db.exists("User Theme Preference", {"user": ADMIN}))

	def test_applying_a_theme_while_paired_replaces_its_own_half(self):
		"""With pairing on, a theme goes to the half that matches its polarity.

		It used to overwrite the light half every time, so applying a theme
		with the OS in dark mode changed nothing on screen, and applying a dark
		theme stored it as the light half as well.
		"""
		light, dark_base = _bundled(0), _bundled(1)
		if not (light and dark_base):
			self.skipTest("need one bundled light and one dark theme")
		other_dark = self._save_custom("nxt-test-other-dark", base=dark_base)

		api.set_active_theme(light)
		api.set_theme_mode("Automatic", dark_theme=dark_base)

		got = api.set_active_theme(other_dark, overrides={"accent": "#123456"})
		self.assertEqual(got["half"], "dark")
		self.assertEqual(got["mode"], "Automatic")

		got = api.get_active_theme()
		self.assertEqual(got["theme"]["name"], light)
		self.assertEqual(got["dark_theme"]["name"], other_dark)
		self.assertEqual(got["overrides"], {})
		self.assertEqual(got["dark_overrides"], {"accent": "#123456"})

	def test_each_half_keeps_its_own_overrides(self):
		light, dark_base = _bundled(0), _bundled(1)
		if not (light and dark_base):
			self.skipTest("need one bundled light and one dark theme")

		api.set_active_theme(light, overrides={"accent": "#111111"})
		api.set_theme_mode("Automatic", dark_theme=dark_base)
		api.set_active_theme(dark_base, overrides={"accent": "#222222"})

		got = api.get_active_theme()
		self.assertEqual(got["overrides"], {"accent": "#111111"})
		self.assertEqual(got["dark_overrides"], {"accent": "#222222"})

		# Leaving Automatic leaves nothing for the dark overrides to belong to.
		api.set_theme_mode("Single")
		got = api.get_active_theme()
		self.assertEqual(got["overrides"], {"accent": "#111111"})
		self.assertEqual(got["dark_overrides"], {})

	def test_the_site_default_cannot_be_deleted(self):
		name = self._save_custom("nxt-test-site-default")
		self._govern(name, 0, [], 1)
		self.assertRaises(frappe.ValidationError, api.delete_custom_theme, name)
		self.assertTrue(frappe.db.exists("Theme Definition", name))
		self._govern(None, 0, [], 1)

	# ------------------------------------------------------------------
	# Saving
	# ------------------------------------------------------------------

	def test_a_key_that_collides_with_a_bundled_theme_gets_its_own(self):
		bundled = _bundled(0)
		payload = dict(_portable(bundled), theme_key=bundled, theme_name="Mine")

		name = api.save_custom_theme(payload, share_public=0)["name"]
		self._made.append(name)

		self.assertNotEqual(name, bundled)
		self.assertTrue(name.startswith(bundled + "-"))
		self.assertEqual(frappe.db.get_value("Theme Definition", name, "theme_name"), "Mine")
		# The bundled theme is untouched.
		self.assertEqual(frappe.db.get_value("Theme Definition", bundled, "is_default"), 1)

	def test_resaving_under_your_own_name_updates_in_place(self):
		name = self._save_custom("nxt-test-resave")
		again = api.save_custom_theme(
			dict(_portable(name), theme_key="nxt-test-resave", theme_name="Renamed"),
			share_public=0,
		)["name"]
		self.assertEqual(again, name)
		self.assertEqual(frappe.db.get_value("Theme Definition", name, "theme_name"), "Renamed")

	def test_renaming_onto_another_of_your_own_themes_is_refused(self):
		"""Names no longer have to be unique across the site, but one
		person's themes still need distinct names or their gallery shows
		two cards nobody can tell apart."""
		self._save_custom("nxt-test-rename-a")
		self._save_custom("nxt-test-rename-b")
		with self.assertRaises(frappe.ValidationError) as caught:
			api.save_custom_theme(
				dict(
					_portable("nxt-test-rename-a"),
					theme_key="nxt-test-rename-a",
					theme_name="Nxt Test Rename B",
				),
				share_public=0,
			)
		self.assertIn("already have", str(caught.exception))

	# ------------------------------------------------------------------
	# Import
	# ------------------------------------------------------------------

	def test_importing_a_theme_you_already_have_makes_a_second_one(self):
		"""An export of your own theme, imported back, used to be matched on
		its name by save_custom_theme() and written over the original."""
		original = self._save_custom("nxt-test-import")
		before = frappe.db.get_value("Theme Definition", original, ["theme_name", "accent"], as_dict=True)

		payload = api.export_theme(original)
		payload["theme"]["accent"] = "#123456"
		imported = api.import_theme(payload, share_public=0)["name"]
		self._made.append(imported)

		self.assertNotEqual(imported, original)
		got = frappe.db.get_value("Theme Definition", imported, ["theme_name", "accent"], as_dict=True)
		self.assertEqual(got.theme_name, f"{before.theme_name} (2)")
		self.assertEqual(got.accent, "#123456")
		# The original is exactly as it was.
		self.assertEqual(
			frappe.db.get_value("Theme Definition", original, ["theme_name", "accent"], as_dict=True),
			before,
		)

	def test_the_sidebar_skin_travels_with_an_export(self):
		original = self._save_custom("nxt-test-sidebar-export")
		frappe.db.set_value(
			"Theme Definition",
			original,
			{"sidebar_style": "Solid", "sidebar_bg": "#1d4ed8", "icon_tints": 1},
		)
		payload = api.export_theme(original)
		self.assertEqual(payload["theme"]["sidebar_style"], "Solid")

		imported = api.import_theme(payload, share_public=0)["name"]
		self._made.append(imported)
		got = frappe.db.get_value(
			"Theme Definition", imported, ["sidebar_style", "sidebar_bg", "icon_tints"], as_dict=True
		)
		self.assertEqual((got.sidebar_style, got.sidebar_bg, got.icon_tints), ("Solid", "#1d4ed8", 1))

	def test_clearing_a_sidebar_colour_goes_back_to_auto(self):
		"""Empty means "derive it" for the sidebar colours, so a resave with
		one cleared has to clear it on the row — other fields keep theirs."""
		name = self._save_custom("nxt-test-sidebar-clear")
		frappe.db.set_value("Theme Definition", name, {"sidebar_style": "Solid", "sidebar_bg": "#1d4ed8"})
		api.save_custom_theme(
			dict(_portable(name), theme_key=name, sidebar_bg="", accent=""),
			share_public=0,
		)
		got = frappe.db.get_value("Theme Definition", name, ["sidebar_bg", "accent"], as_dict=True)
		self.assertFalse(got.sidebar_bg)
		self.assertTrue(got.accent)

	def test_sidebar_overrides_are_kept_and_cleaned(self):
		api.set_active_theme(
			_bundled(0),
			overrides={"sidebar_style": "Tinted", "sidebar_pattern": "1", "sidebar_bg": "url(x)"},
		)
		got = api.get_active_theme()["overrides"]
		self.assertEqual(got, {"sidebar_style": "Tinted", "sidebar_pattern": 1})

	# ------------------------------------------------------------------
	# Sounds
	# ------------------------------------------------------------------

	def test_a_sound_must_be_a_file_this_site_serves(self):
		for bad in (
			"javascript:alert(1)",
			"https://example.com/x.mp3",
			"//example.com/x.mp3",
			"/etc/passwd",
			"/files/../../x.mp3",
			"/files/x.exe",
			"/assets/nexus_theme/sounds/save-1.wav?x=<script>",
		):
			with self.subTest(url=bad):
				self.assertRaises(frappe.ValidationError, api.set_user_sound, "save", bad, 0.5)

		api.set_user_sound("save", SOUND, 0.5)
		self.assertEqual(api.get_user_sounds()["mapping"]["save"]["url"], SOUND)

	def test_the_names_frappe_keeps_on_upload_are_accepted(self):
		# An upload named like this used to be refused after the fact,
		# stranding the File it had just created.
		for url in ("/files/Ben's chime & bell.aiff", "/private/files/Ding (1).opus"):
			with self.subTest(url=url):
				api.set_user_sound("save", url, 0.5)
				self.assertEqual(api.get_user_sounds()["mapping"]["save"]["url"], url)

	def test_a_volume_is_kept_without_a_file(self):
		api.set_user_sound("submit", None, 0.2)
		row = api.get_user_sounds()["mapping"]["submit"]
		self.assertIsNone(row["url"])
		self.assertAlmostEqual(row["volume"], 0.2)
		# A later file keeps that volume; a later volume keeps the file.
		api.set_user_sound("submit", SOUND, 0.2)
		api.set_user_sound("submit", None, 0.9)
		row = api.get_user_sounds()["mapping"]["submit"]
		self.assertEqual(row["url"], SOUND)
		self.assertAlmostEqual(row["volume"], 0.9)

	def test_sound_writes_honour_the_site_switch(self):
		self._govern(None, 0, [], 0)
		self.assertRaises(frappe.ValidationError, api.set_user_sound, "save", SOUND, 0.5)
		self.assertRaises(frappe.ValidationError, api.toggle_user_sounds, 1)
		self._govern(None, 0, [], 1)

	def test_the_site_switch_withholds_custom_sounds_but_not_audio(self):
		api.set_user_sound("save", SOUND, 0.5)
		self._govern(None, 0, [], 0)
		payload = api.get_user_sounds()
		# Off means "no custom sounds", not "silence": stock sounds still
		# play, so `enabled` stays up while the mapping is withheld.
		self.assertEqual(payload["allowed"], 0)
		self.assertEqual(payload["enabled"], 1)
		self.assertEqual(payload["mapping"], {})
		self._govern(None, 0, [], 1)
		self.assertEqual(api.get_user_sounds()["mapping"]["save"]["url"], SOUND)

	def test_the_login_stamp_is_the_users_last_login(self):
		frappe.db.set_value("User", ADMIN, "last_login", "2026-09-24 09:30:00")
		self.assertEqual(api.get_user_sounds()["login_stamp"], "2026-09-24 09:30:00")

	# ------------------------------------------------------------------
	# Role provisioning
	# ------------------------------------------------------------------

	def _fresh_user(self, email: str, **extra):
		if frappe.db.exists("User", email):
			frappe.delete_doc("User", email, force=True, ignore_permissions=True)
		return frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Role Test",
				"send_welcome_email": 0,
				**extra,
			}
		).insert(ignore_permissions=True)

	def _has_theme_role(self, email: str) -> bool:
		return bool(frappe.db.exists("Has Role", {"parent": email, "role": THEME_USER_ROLE}))

	def test_a_user_promoted_to_the_desk_later_gets_the_role_then(self):
		email = "nxt-role-later@example.com"
		u = self._fresh_user(email)
		try:
			# No Desk role at creation: Frappe makes this a Website User, and
			# it must NOT get ours.
			self.assertEqual(u.user_type, "Website User")
			self.assertFalse(self._has_theme_role(email))

			# Promoted on a later save — the case after_insert never saw.
			u.add_roles("System Manager")
			self.assertEqual(frappe.db.get_value("User", email, "user_type"), "System User")
			self.assertTrue(self._has_theme_role(email))
		finally:
			frappe.delete_doc("User", email, force=True, ignore_permissions=True)

	def test_a_desk_user_created_with_a_role_gets_it_at_once(self):
		email = "nxt-role-now@example.com"
		u = self._fresh_user(email, roles=[{"role": "System Manager"}])
		try:
			self.assertEqual(u.user_type, "System User")
			self.assertTrue(self._has_theme_role(email))
		finally:
			frappe.delete_doc("User", email, force=True, ignore_permissions=True)
