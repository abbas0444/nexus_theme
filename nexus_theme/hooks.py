app_name = "nexus_theme"
app_title = "Nexus Theme"
app_publisher = "Abbas Raza"
# --- Frappe 15 branch -------------------------------------------------------
# This branch targets Frappe/ERPNext 15. It is the same app as `main`, which
# targets 16; only the handful of places where the two frameworks differ are
# changed. See "Which branch do I need?" in the README.
# ---------------------------------------------------------------------------

app_description = "Per-user theme and sound personalization for the Frappe & ERPNext Desk — a live color editor with WCAG contrast validation, 17 bundled themes, 8 curated accessible palettes, and a Sound Studio for customizing audio on save, submit, login, notifications and more."
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
	"theme_switcher.bundle.css",
	"sound_studio.bundle.css",
]
app_include_js = [
	"theme_manager.bundle.js",
	"theme_switcher.bundle.js",
	"theme_editor.bundle.js",
	# Adds every Theme Definition to Frappe's own "Switch Theme" dialog
	# (avatar menu → Toggle Theme). Must load after theme_manager,
	# which it delegates to when applying a theme.
	"native_theme_switcher.bundle.js",
	# Navbar logo / favicon from Theme Settings. No-op until one is set.
	"brand_kit.bundle.js",
	# Shared factory behind the /app/theme-studio and /app/sound-studio
	# launcher pages, which is how the two dialogs reach the Workspace —
	# a workspace link cannot call a function.
	"studio_page.bundle.js",
	"sound_manager.bundle.js",
	"sound_studio.bundle.js",
]

# Login page and public website. The stylesheet is inert unless
# website.update_website_context injects the theme's CSS variables, which it
# only does when an admin ticks "Apply to Login & Website" in Theme Settings.
web_include_css = ["web_theme.bundle.css"]
# Mirrors the injected theme's polarity onto <html data-theme> so website
# CSS keyed off [data-theme="dark"] matches the site theme.
web_include_js = ["web_theme.bundle.js"]

# Register an <audio id="sound-X"> element for every supported Desk event so
# the app is fully self-contained — it never depends on Frappe's stock sounds
# staying in place. Each default points at preset 1 (the "apt" sound) of that
# event; all files are original tones synthesised by tools/generate_sounds.py.
# Users can override any of them per-event via Sound Studio.
sounds = [
	{"name": event, "src": f"/assets/nexus_theme/sounds/{event}-1.wav", "volume": 0.3}
	for event in (
		"save",
		"submit",
		"cancel",
		"delete",
		"error",
		"email",
		"alert",
		"click",
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

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

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
