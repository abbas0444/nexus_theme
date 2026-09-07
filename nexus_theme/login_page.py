"""A themed login page for this app, rendered only when an admin turns it on.

Frappe resolves a web route by asking every renderer in turn whether it can
handle it, and the `page_renderer` hook puts an app's own renderers at the
front of that queue. That is the supported way to take over a route from an
app, and it is the only thing this feature needs: no file in Frappe, in
ERPNext or in any other app is touched, and nothing here runs for any path
other than `/login`.

The stock Frappe login page stays exactly where it is. `can_render()` returns
False when the switch in Theme Settings is off, when the template is missing,
or when anything at all raises — and Frappe then renders its own page as
usual. That fallback is deliberate: a login page is the one screen that must
never break, so every question this module asks is allowed to fail.

The markup keeps every element id and class that Frappe's own
`templates/includes/login/login.js` binds to, so password login, the error
banner, forgot password, sign up, the email login link, social logins, LDAP
and two-factor all keep working. Only the layout and the styling are ours.
"""

import json
import os

import frappe
from frappe.website.page_renderers.template_page import TemplatePage

from nexus_theme.utils.web_css import VAR_MAP, theme_css_rules

APP_NAME = "nexus_theme"
TEMPLATE_PATH = os.path.join("templates", "nexus_login", "nexus_login.html")

# Only the login route. Frappe reaches sign-up, forgot-password and the email
# link through hashes on this same page, so there is nothing else to claim.
LOGIN_PATHS = ("login",)

# Shown when an admin has not written their own copy. Deliberately plain:
# the panel is theirs to fill in, and invented claims would be worse than
# a quiet, honest default.
DEFAULT_HEADLINE = "Welcome back"
DEFAULT_SUBHEADLINE = "Sign in to pick up where you left off."

MAX_PANEL_POINTS = 6


def _settings() -> dict:
	from nexus_theme.nexus_theme.doctype.theme_settings.theme_settings import get_settings

	return get_settings()


def is_enabled() -> bool:
	"""True when an admin has switched the Nexus login page on.

	Never raises: a missing DocType, an un-migrated site or a broken cache
	all mean "use Frappe's own login page", which is always safe.
	"""
	try:
		return bool(_settings().get("use_nexus_login"))
	except Exception:
		return False


class NexusLoginPage(TemplatePage):
	"""Renders `/login` from this app's template instead of Frappe's.

	Everything except the template location and the extra context comes from
	`TemplatePage`, so the response is built, cached and CSRF-stamped exactly
	like any other Frappe web page.
	"""

	def set_template_path(self):
		"""Point at our template, or leave `template_path` empty.

		`TemplatePage.can_render()` is simply "did this find a template", so
		leaving it empty is how this renderer declines a request and lets
		Frappe carry on down its own list of renderers.

		The cheap path check comes first: this method runs for every website
		request on the site, and must not touch the database for any of them
		except the login page.
		"""
		if self.path not in LOGIN_PATHS:
			return
		try:
			if not is_enabled():
				return
			app_path = frappe.get_app_path(APP_NAME)
			file_path = os.path.join(app_path, TEMPLATE_PATH)
			if not os.path.isfile(file_path):
				return
		except Exception:
			# Fall back to Frappe's login page rather than fail the request.
			return

		self.app = APP_NAME
		self.app_path = app_path
		self.file_dir = os.path.dirname(TEMPLATE_PATH)
		self.basename = os.path.splitext(file_path)[0]
		self.template_path = TEMPLATE_PATH
		self.basepath = os.path.dirname(file_path)
		self.filename = os.path.basename(file_path)
		self.name = os.path.splitext(self.filename)[0]

	def update_context(self):
		super().update_context()

		# Never serve a cached login page: the same reasoning as Frappe's own
		# `www/login.py`, which sets `no_cache` at module level.
		self.context.no_cache = 1

		# Tells nexus_theme/website.py to leave the login background alone —
		# this page places that image itself, in the side panel.
		frappe.local.flags.nexus_login_page = True

		# Frappe's own login context: social logins, LDAP, sign-up template,
		# two-factor, the "already signed in" redirect. Reused whole so this
		# page can never fall behind the stock one.
		from frappe.www import login as frappe_login

		frappe_login.get_context(self.context)

		self.context.update(get_login_context())


def app_name() -> str:
	"""The site's own name, resolved the way Frappe's login page resolves it."""
	from frappe import _

	try:
		return (
			frappe.get_website_settings("app_name") or frappe.get_system_settings("app_name") or _("Frappe")
		)
	except Exception:
		return "Frappe"


def brand(settings: dict, fallback_logo: str | None = None) -> dict:
	"""The name and logo shown above the sign-in form.

	An admin can name the sign-in screen whatever they like; left empty it is
	the site's own app name and logo, so the page looks like the site rather
	than like this app.
	"""
	return {
		"name": (settings.get("login_brand_name") or "").strip() or app_name(),
		"logo": public_file(settings.get("login_brand_logo"))
		or public_file(settings.get("navbar_logo"))
		or fallback_logo,
	}


def default_footnote(brand_name: str) -> str:
	"""The small print under the sign-in button, when nobody has typed any.

	Built from the brand name and this year so it never names the wrong
	company and never goes stale on the first of January.
	"""
	from datetime import date

	name = (brand_name or "").strip()
	return f"\u00a9 {date.today().year} {name}".strip() if name else ""


def copy_for(settings: dict, brand_name: str | None = None) -> dict:
	"""The words on the page. Shared by the live page and the Theme Studio
	preview, so the two can never drift apart."""
	return {
		"subtitle": (settings.get("login_subtitle") or "").strip(),
		"headline": (settings.get("login_headline") or "").strip() or DEFAULT_HEADLINE,
		"subheadline": (settings.get("login_subheadline") or "").strip() or DEFAULT_SUBHEADLINE,
		"points": panel_points(settings.get("login_points")),
		"stat": (settings.get("login_stat") or "").strip(),
		"stat_note": (settings.get("login_stat_note") or "").strip(),
		"footnote": (settings.get("login_footnote") or "").strip() or default_footnote(brand_name),
		"image": public_file(settings.get("login_background")),
	}


def preview_payload() -> dict:
	"""Everything Theme Studio needs to draw the sign-in screen.

	None of it is private: every value is rendered on a page served to
	anonymous visitors.
	"""
	try:
		settings = _settings()
	except Exception:
		settings = {}

	fallback_logo = None
	try:
		from frappe.core.doctype.navbar_settings.navbar_settings import get_app_logo

		fallback_logo = get_app_logo()
	except Exception:
		pass

	marks = brand(settings, fallback_logo)
	payload = {
		"enabled": 1 if settings.get("use_nexus_login") else 0,
		"brand_name": marks["name"],
		"brand_logo": marks["logo"],
	}
	payload.update(copy_for(settings, marks["name"]))
	return payload


def get_login_context() -> dict:
	"""The extra values our template needs, on top of Frappe's own."""
	try:
		settings = _settings()
	except Exception:
		settings = {}

	theme = _resolve_theme(settings)
	marks = brand(settings)
	words = copy_for(settings, marks["name"])

	return {
		# base.html renders this on <body>; the stylesheet uses it to clear the
		# website margins this page does not want.
		"body_class": "nxlogin-body",
		"nxlogin_theme_css": theme_css_rules(theme) if theme else "",
		"nxlogin_theme_js": remembered_theme_script(),
		"nxlogin_is_dark": 1 if (theme or {}).get("is_dark") else 0,
		"nxlogin_brand_name": marks["name"],
		"nxlogin_logo": marks["logo"],
		"nxlogin_image": words["image"],
		"nxlogin_headline": words["headline"],
		"nxlogin_subheadline": words["subheadline"],
		"nxlogin_points": words["points"],
		"nxlogin_stat": words["stat"],
		"nxlogin_stat_note": words["stat_note"],
		"nxlogin_footnote": words["footnote"],
		"nxlogin_subtitle": words["subtitle"],
	}


def public_file(url: str | None) -> str | None:
	"""Drop a file the visitor could not fetch anyway.

	Nobody is signed in on this page, so a Theme Settings image uploaded as a
	private file answers 403 and the browser draws a broken image. Returning
	None instead lets the template fall back to the site logo, or leave the
	space empty.
	"""
	url = (url or "").strip()
	if not url or url.startswith("/private/"):
		return None
	return url


def _resolve_theme(settings: dict) -> dict | None:
	"""The theme this page paints with: the site default, if there is one.

	Unlike the rest of the website, this does not wait for "Apply to Login &
	Website". Turning this page on is itself the decision to have the app
	style the login screen; a themed page that ignored the site's own theme
	would be the surprising behaviour.
	"""
	name = settings.get("site_default_theme")
	if not name:
		return None
	try:
		return frappe.db.get_value("Theme Definition", name, [*VAR_MAP, "is_dark"], as_dict=True)
	except Exception:
		return None


def panel_points(raw) -> list[str]:
	"""The side panel's bullet list: one point per line, blanks dropped."""
	if not raw:
		return []
	points = [line.strip() for line in str(raw).splitlines()]
	return [p for p in points if p][:MAX_PANEL_POINTS]


# The value theme_manager.js writes to localStorage when a user applies a
# theme on the Desk, and the CSS custom properties it maps the fields to.
STORAGE_KEY = "theme:active"

# Runs in <head>, before the body paints, so a returning visitor sees their
# own theme rather than the site default flashing first. Values are written
# through setProperty (never string-concatenated into CSS) and are checked
# against the same shapes the server allows, so a hand-edited cache can only
# ever produce a wrong colour in that one browser.
_REMEMBERED_THEME_JS = """
(function () {
  try {
    var MAP = __VAR_MAP__;
    var raw = window.localStorage && localStorage.getItem("__KEY__");
    if (!raw) return;
    var cached = JSON.parse(raw);
    var theme = cached.theme;
    if (cached.mode === "Automatic" && cached.dark_theme) {
      var prefersDark =
        window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
      theme = prefersDark ? cached.dark_theme : cached.light_theme || cached.theme;
    }
    if (!theme || typeof theme !== "object") return;

    var COLOR = /^#[0-9a-fA-F]{3,8}$/;
    var TOKEN = /^[-\\w\\s,.'"()%]+$/;
    var root = document.documentElement;

    var put = function (field, value) {
      var prop = MAP[field];
      if (!prop || value === undefined || value === null || value === "") return;
      value = String(value);
      if (!COLOR.test(value) && !TOKEN.test(value)) return;
      root.style.setProperty(prop, value);
    };

    Object.keys(MAP).forEach(function (field) {
      put(field, theme[field]);
    });
    var overrides = cached.overrides || {};
    Object.keys(overrides).forEach(function (field) {
      put(field, overrides[field]);
    });

    var polarity = theme.is_dark ? "dark" : "light";
    root.style.setProperty("color-scheme", polarity);
    root.setAttribute("data-theme", polarity);
  } catch (e) {
    /* a remembered theme is a nicety; never block the login page over it */
  }
})();
"""


def remembered_theme_script() -> str:
	"""The inline head script that repaints the page in the visitor's own theme."""
	return (
		_REMEMBERED_THEME_JS.replace("__VAR_MAP__", json.dumps(VAR_MAP, sort_keys=True))
		.replace("__KEY__", STORAGE_KEY)
		.strip()
	)
