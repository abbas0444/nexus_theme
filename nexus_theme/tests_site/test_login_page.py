"""The Nexus login page must be opt-in, complete, and safe to fall back from.

Two things are load-bearing here and both are tested by rendering the real
route:

* with the switch off, `/login` is still Frappe's own page, exactly the page
  the site had before this app was installed;
* with it on, the page carries every element id and class that Frappe's own
  login script binds to. A missing one would look fine and quietly break
  signing in, which is the one screen that must never break.
"""

import re

import frappe
from frappe.tests.utils import FrappeTestCase
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from nexus_theme import login_page
from nexus_theme.nexus_theme.doctype.theme_settings.theme_settings import clear_settings_cache

# Ids and classes frappe/templates/includes/login/login.js selects.
REQUIRED_HOOKS = (
	'class="for-login"',
	"form-login",
	"form-forgot",
	"form-login-with-email-link",
	'id="login_email"',
	'id="login_password"',
	'id="forgot_email"',
	'id="login_with_email_link_email"',
	"page-card-body",
	"page-card-actions",
	"field-error",
	"login-error-banner",
	"login-success-banner",
	"resend-link",
	"btn-resend-link",
	"btn-login",
	"btn-forgot",
	"login-content",
	"page-card",
)

STOCK_MARKER = "<!-- login.html -->"


def _guest_request(path="/login"):
	frappe.local.request = Request(EnvironBuilder(path=path, method="GET").get_environ())
	frappe.local.request_ip = "127.0.0.1"


def _render_login():
	from frappe.website.serve import get_response_content

	_guest_request()
	return get_response_content("login")


class TestNexusLoginPage(FrappeTestCase):
	def setUp(self):
		self._user = frappe.session.user
		frappe.set_user("Guest")

	def tearDown(self):
		frappe.set_user(self._user)
		frappe.db.rollback()
		clear_settings_cache()

	def _switch(self, on, **values):
		settings = frappe.get_single("Theme Settings")
		settings.use_nexus_login = 1 if on else 0
		for field, value in values.items():
			setattr(settings, field, value)
		settings.save(ignore_permissions=True)
		clear_settings_cache()

	# -- the switch ---------------------------------------------------------

	def test_off_by_default_on_a_fresh_settings_record(self):
		from nexus_theme.nexus_theme.doctype.theme_settings.theme_settings import DEFAULTS

		self.assertEqual(DEFAULTS["use_nexus_login"], 0)

	def test_renderer_declines_every_route_but_login(self):
		self._switch(True)
		_guest_request()
		for path in ("index", "about", "app", "login/extra", "update-password", "api/method/login"):
			self.assertFalse(
				login_page.NexusLoginPage(path).can_render(),
				f"the renderer claimed /{path}",
			)

	def test_an_empty_path_means_the_current_request(self):
		# Frappe's BaseRenderer falls back to frappe.local.request.path when a
		# renderer is built with no path. Its own resolver always passes a real
		# endpoint, so this only matters to callers that construct one by hand.
		self._switch(True)
		_guest_request("/about")
		self.assertFalse(login_page.NexusLoginPage("").can_render())
		_guest_request("/login")
		self.assertTrue(login_page.NexusLoginPage("").can_render())

	def test_renderer_declines_login_while_the_switch_is_off(self):
		self._switch(False)
		self.assertFalse(login_page.NexusLoginPage("login").can_render())

	def test_renderer_claims_login_once_the_switch_is_on(self):
		self._switch(True)
		self.assertTrue(login_page.NexusLoginPage("login").can_render())

	# -- rendering ----------------------------------------------------------

	def test_stock_login_page_is_served_while_the_switch_is_off(self):
		self._switch(False)
		html = _render_login()
		self.assertIn(STOCK_MARKER, html)
		self.assertNotIn("nxlogin", html)

	def test_nexus_page_is_served_once_the_switch_is_on(self):
		self._switch(True)
		html = _render_login()
		self.assertIn("nxlogin", html)
		self.assertNotIn(STOCK_MARKER, html)

	def test_every_element_the_login_script_needs_is_present(self):
		self._switch(True)
		html = _render_login()
		for hook in REQUIRED_HOOKS:
			self.assertIn(hook, html, f"{hook} is missing; login.js binds to it")
		self.assertIn("login.bind_events", html, "Frappe's own login script is not loaded")

	def test_page_links_its_own_stylesheet_and_not_frappes(self):
		self._switch(True)
		html = _render_login()
		links = re.findall(r'<link[^>]*href="([^"]+)"', html)
		self.assertTrue(any("nexus_login.bundle" in link for link in links), links)
		# Frappe's login stylesheet is replaced here, not layered under ours.
		self.assertFalse(any("/login.bundle" in link for link in links), links)

	def test_admin_copy_is_escaped_not_injected(self):
		# Frappe's own sanitiser already strips <script> on save; what reaches
		# the template must still be escaped, so markup it lets through
		# (<b>, quotes) shows as text rather than becoming part of the page.
		self._switch(
			True,
			login_headline="Safe <b>NXTOKEN</b> <script>alert(1)</script>",
			login_footnote='"><img src=x onerror=alert(1)>',
		)
		html = _render_login()
		self.assertNotIn("<b>NXTOKEN</b>", html)
		self.assertIn("&lt;b&gt;NXTOKEN&lt;/b&gt;", html)
		self.assertNotIn("<script>alert(1)</script>", html)
		self.assertNotIn("onerror=alert(1)", html)

	def test_theme_variables_are_injected_from_the_site_default_theme(self):
		theme = frappe.get_all("Theme Definition", filters={"is_default": 1}, limit=1, pluck="name")[0]
		self._switch(True, site_default_theme=theme)
		html = _render_login()
		self.assertIn("--theme-bg-primary", html)
		self.assertIn("nexus-login-theme", html)

	def test_page_is_not_cached_for_the_next_visitor(self):
		self._switch(True)
		renderer = login_page.NexusLoginPage("login")
		_guest_request()
		renderer.get_html()
		self.assertTrue(renderer.context.no_cache)

	# -- context helpers ----------------------------------------------------

	def test_panel_points_are_one_per_line_and_capped(self):
		self.assertEqual(login_page.panel_points(None), [])
		self.assertEqual(login_page.panel_points("  "), [])
		self.assertEqual(login_page.panel_points("a\n\n b \nc"), ["a", "b", "c"])
		self.assertEqual(len(login_page.panel_points("\n".join(str(i) for i in range(20)))), 6)

	def test_private_files_are_never_offered_to_anonymous_visitors(self):
		self.assertIsNone(login_page.public_file("/private/files/logo.png"))
		self.assertIsNone(login_page.public_file(""))
		self.assertIsNone(login_page.public_file(None))
		self.assertEqual(login_page.public_file("/files/logo.png"), "/files/logo.png")

	def test_remembered_theme_script_is_self_contained(self):
		script = login_page.remembered_theme_script()
		self.assertIn("theme:active", script)
		self.assertIn("--theme-accent", script)
		# It is written inline into a <script> block.
		self.assertNotIn("</script", script)

	def test_enabled_check_never_raises(self):
		original = login_page._settings

		def boom():
			raise RuntimeError("settings unavailable")

		login_page._settings = boom
		try:
			self.assertFalse(login_page.is_enabled())
			self.assertFalse(login_page.NexusLoginPage("login").can_render())
		finally:
			login_page._settings = original
