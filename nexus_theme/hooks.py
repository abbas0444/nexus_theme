app_name = "nexus_theme"
app_title = "Nexus Theme"
app_publisher = "Abbas Raza"
app_description = "Theme Studio, Sound Studio and a Permission Inspector for the Frappe & ERPNext Desk — 17 bundled themes with a live colour editor and WCAG contrast checks, per-user sounds for save, submit and alerts, an optional themed sign-in page, and a plain-language view of who can do what."
app_email = "abbasraza0444@gmail.com"
app_license = "MIT"
# Shown next to the app wherever Frappe lists installed apps.
app_logo_url = "/assets/nexus_theme/images/logo.svg"

# Apps
# ------------------

# required_apps = []

# Puts the app on the Desk's apps screen and gives it a Desktop Icon on the
# home grid. Frappe builds that icon from these four keys
# (create_desktop_icons_from_installed_apps), so without this hook the app has
# no tile at all and is reachable only from the avatar dropdown.
#
# The route has to resolve to something real: the app's own UI is dialog-based,
# so it points at the Workspace shipped in nexus_theme/workspace/, which
# collects the theme and sound entry points in one place.
add_to_apps_screen = [
	{
		"name": "nexus_theme",
		"logo": "/assets/nexus_theme/images/logo.svg",
		"title": "Nexus Theme",
		"route": "/app/nexus-theme",
		"has_permission": "nexus_theme.api.check_app_permission",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = [
	"theme_variables.bundle.css",
	# Compact / Comfortable / Spacious. Keyed off html[data-density] and
	# not off the theme: inert until density.js sets the attribute.
	"density.bundle.css",
	"theme_switcher.bundle.css",
	"sound_studio.bundle.css",
	"command_palette.bundle.css",
	"whats_new.bundle.css",
	# Mini rail. Keyed off html[data-nexus-rail-host], which only
	# sidebar_rail.js sets, and only on screens wide enough for it.
	"sidebar_rail.bundle.css",
	# Per-theme sidebar skin (Tinted / Solid / Gradient) and module icon
	# tints. Last so it wins ties with the rules above; inert until
	# theme_manager.js sets html[data-sidebar-style] or [data-icon-tints].
	"sidebar_skin.bundle.css",
]
app_include_js = [
	"theme_manager.bundle.js",
	# Sets html[data-density] from boot before anything draws and exposes
	# window.NexusDensity. Before theme_switcher, whose Density control
	# calls it.
	"density.bundle.js",
	"theme_switcher.bundle.js",
	"theme_editor.bundle.js",
	# Adds every Theme Definition to Frappe's own "Switch Theme" dialog
	# (sidebar → Display → Toggle Theme). Must load after theme_manager,
	# which it delegates to when applying a theme.
	"native_theme_switcher.bundle.js",
	# Navbar logo / favicon from Theme Settings. No-op until one is set.
	"brand_kit.bundle.js",
	# Adds "Theme Studio" and "Sound Settings" to the avatar dropdown on
	# Frappe v16's Desk. That Desk hides the classic navbar, so the Navbar
	# Settings items registered by install.py never render there and the app
	# would otherwise have no entry point in the UI.
	"desktop_menu.bundle.js",
	# Shared factory behind the /app/theme-studio and /app/sound-studio
	# launcher pages, which is how the two dialogs reach the Workspace —
	# a workspace link cannot call a function.
	"studio_page.bundle.js",
	"sound_manager.bundle.js",
	"sound_studio.bundle.js",
	# Ctrl+K / ⌘K command palette. Late on purpose: it takes the key over
	# from Frappe's awesomebar and reads the openers the bundles above
	# define (openThemeSwitcher, openSoundStudio, ThemeManager, SoundManager).
	"command_palette.bundle.js",
	# Shows each person a short "What's new" card once after an upgrade
	# to a release that has something to say (whats_new.py decides). After
	# the palette, so the card can register its own command there.
	"whats_new.bundle.js",
	# Mini rail: drives Frappe 16's own collapsed sidebar (or Frappe 15's
	# page side section), stores the choice per user, adds Ctrl+Shift+B and
	# hover-to-peek. After the palette, whose register() it calls.
	"sidebar_rail.bundle.js",
	# window.openNexusHome() and, while the Nexus home page is switched on
	# in Theme Settings, an "Open Home" palette command. After the palette,
	# which it registers with. The page's own script and styles live in
	# nexus_theme/page/nexus_home and load only when it is opened.
	"home_page.bundle.js",
]

# Login page and public website. The stylesheet is inert unless
# website.update_website_context injects the theme's CSS variables, which it
# only does when an admin ticks "Apply to Login & Website" in Theme Settings.
web_include_css = ["web_theme.bundle.css"]
# Mirrors the injected theme's polarity onto <html data-theme> so website
# CSS keyed off [data-theme="dark"] matches the site theme.
web_include_js = ["web_theme.bundle.js"]

# Register an <audio id="sound-X"> element for each Desk event Frappe has no
# sound of its own for. desk.html prints one element per entry from every
# app's hook, and play_sound() takes the first match by id, so re-declaring
# click, submit, cancel, delete, error, email or alert here would only add a
# duplicate element that never plays: Frappe's stock sound stays the default
# for those. Each default below points at preset 1 (the "apt" sound) of that
# event; all files are original tones synthesised by tools/generate_sounds.py.
# The presets for every event, stock ones included, are offered in Sound
# Studio, where users can pick one or upload their own per event. There is
# no "save" entry either: the Save button plays "click", and Sound Studio's
# Save row maps onto it (see USER_TO_FRAPPE in sound_manager.js).
sounds = [
	{"name": event, "src": f"/assets/nexus_theme/sounds/{event}-1.wav", "volume": 0.3}
	for event in (
		"notification",
		"login",
		"logout",
		"missing_fields",
	)
]

# include js, css files in header of web template
# web_include_css = "/assets/nexus_theme/css/theme.css"
# web_include_js = "/assets/nexus_theme/js/theme.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "nexus_theme/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "nexus_theme/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "nexus_theme.utils.jinja_methods",
# 	"filters": "nexus_theme.utils.jinja_filters"
# }

# Sidebar settings dropdown
# -------------------------
# Frappe v16 replaced the top navbar with the left sidebar, whose settings
# dropdown is drawn from Navbar Settings (sidebar_header.add_navbar_items
# reads `settings_dropdown`). That is how Frappe registers "Toggle Theme",
# and it is the app's way into Theme Studio and Sound Studio.
#
# Declared under this hook, and not only added by install.py, because
# migrate's sync_standard_items() deletes every `is_standard` row that no
# installed app declares: rows added by install alone were removed and put
# back on every migrate, losing their order and any "hidden" tick along the
# way. Listed here they are added once, and kept.
standard_navbar_items = [
	{
		"item_label": "Theme Studio",
		"item_type": "Action",
		"action": "window.openThemeSwitcher && window.openThemeSwitcher()",
		"is_standard": 1,
	},
	{
		"item_label": "Sound Settings",
		"item_type": "Action",
		"action": "window.openSoundStudio && window.openSoundStudio()",
		"is_standard": 1,
	},
]

# Installation
# ------------

# before_install = "nexus_theme.install.before_install"
# Create the "Theme User" role and grant it to every existing Desk user.
after_install = "nexus_theme.install.after_install"
after_migrate = "nexus_theme.install.after_migrate"

# Uninstallation
# ------------

# Remove the "Theme User" role and the synced asset tree on uninstall.
before_uninstall = "nexus_theme.uninstall.before_uninstall"
# after_uninstall = "nexus_theme.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "nexus_theme.utils.before_app_install"
# after_app_install = "nexus_theme.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "nexus_theme.utils.before_app_uninstall"
# after_app_uninstall = "nexus_theme.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "nexus_theme.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# The Theme User role reads Theme Definition without `if_owner` so the
# gallery can list bundled and shared themes — which also let anyone read
# every private theme on the site through /api/resource. These narrow a
# Theme User's reads to the gallery's own rule: bundled, shared, or yours.
permission_query_conditions = {
	"Theme Definition": "nexus_theme.nexus_theme.doctype.theme_definition.theme_definition.get_permission_query_conditions",
}

has_permission = {
	"Theme Definition": "nexus_theme.nexus_theme.doctype.theme_definition.theme_definition.has_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# Grant the "Theme User" role to every Desk user so theme and sound
# self-service works out of the box. after_insert covers a user created with
# a Desk role; on_update covers one promoted to System User later, which
# Frappe does on any save that adds a Desk role. Website users are skipped
# either way.
doc_events = {
	"User": {
		"after_insert": "nexus_theme.install.assign_theme_role",
		"on_update": "nexus_theme.install.assign_theme_role",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"nexus_theme.tasks.all"
# 	],
# 	"daily": [
# 		"nexus_theme.tasks.daily"
# 	],
# 	"hourly": [
# 		"nexus_theme.tasks.hourly"
# 	],
# 	"weekly": [
# 		"nexus_theme.tasks.weekly"
# 	],
# 	"monthly": [
# 		"nexus_theme.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "nexus_theme.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "nexus_theme.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "nexus_theme.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["nexus_theme.utils.before_request"]
# after_request = ["nexus_theme.utils.after_request"]

# Job Events
# ----------
# before_job = ["nexus_theme.utils.before_job"]
# after_job = ["nexus_theme.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"nexus_theme.auth.validate"
# ]

# Boot session
# ------------
# Inject active theme into bootinfo so first paint is themed without a round-trip.
boot_session = "nexus_theme.api.extend_boot_session"

# Website
# -------
# Theme the login page and public web pages from the site default theme.
update_website_context = "nexus_theme.website.update_website_context"

# Takes over /login with this app's own two-column sign-in page, but only when
# an admin ticks "Use the Nexus Login Page" in Theme Settings. The renderer
# declines every other route and, with the switch off or on any error, hands
# the request straight back to Frappe's standard login page.
page_renderer = ["nexus_theme.login_page.NexusLoginPage"]

# Fixtures
# --------
# Ship 10 default themes with the app; exported/imported via bench migrate.
fixtures = [
	{"dt": "Theme Definition", "filters": [["is_default", "=", 1]]},
]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
