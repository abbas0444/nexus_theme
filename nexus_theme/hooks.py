app_name = "nexus_theme"
app_title = "Nexus Theme"
app_publisher = "Abbas Raza"
app_description = "Per-user theme and sound personalization for the Frappe & ERPNext Desk — a live color editor with WCAG contrast validation, 17 bundled themes, 8 curated accessible palettes, and a Sound Studio for customizing audio on save, submit, login, notifications and more."
app_email = "abbasraza0444@gmail.com"
app_license = "MIT"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "nexus_theme",
# 		"logo": "/assets/nexus_theme/logo.png",
# 		"title": "Themes",
# 		"route": "/theme",
# 		"has_permission": "nexus_theme.api.permission.has_app_permission"
# 	}
# ]

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

# Grant the "Theme User" role to every newly created Desk user so theme and
# sound self-service works out of the box. Website users are skipped.
doc_events = {
	"User": {
		"after_insert": "nexus_theme.install.assign_theme_role",
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

