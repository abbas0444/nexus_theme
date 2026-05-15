app_name = "theme"
app_title = "Theme Studio"
app_publisher = "Abbas Raza"
app_description = "Premium theme & sound customization for Frappe — live preview, WCAG contrast guard, curated palettes, and per-user sound packs."
app_email = "abbasraza0444@gmail.com"
app_license = "MIT"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "theme",
# 		"logo": "/assets/theme/logo.png",
# 		"title": "Themes",
# 		"route": "/theme",
# 		"has_permission": "theme.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = [
	"/assets/theme/css/theme_variables.css",
	"/assets/theme/css/theme_switcher.css",
	"/assets/theme/css/sound_studio.css",
]
app_include_js = [
	"/assets/theme/js/theme_manager.js",
	"/assets/theme/js/theme_switcher.js",
	"/assets/theme/js/theme_editor.js",
	"/assets/theme/js/sound_manager.js",
	"/assets/theme/js/sound_studio.js",
]

# Register the new 'notification' sound with Frappe so the <audio id="sound-notification">
# element is rendered at boot. Reuses Frappe's stock alert.mp3 as the default — users
# can upload their own via Sound Studio to override it.
sounds = [
	{"name": "notification", "src": "/assets/frappe/sounds/alert.mp3", "volume": 0.3},
	{"name": "login", "src": "/assets/frappe/sounds/chime.mp3", "volume": 0.3},
	{"name": "logout", "src": "/assets/frappe/sounds/cancel.mp3", "volume": 0.3},
	{"name": "missing_fields", "src": "/assets/frappe/sounds/error.mp3", "volume": 0.3},
]

# include js, css files in header of web template
# web_include_css = "/assets/theme/css/theme.css"
# web_include_js = "/assets/theme/js/theme.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "theme/public/scss/website"

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
# app_include_icons = "theme/public/icons.svg"

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
# 	"methods": "theme.utils.jinja_methods",
# 	"filters": "theme.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "theme.install.before_install"
# after_install = "theme.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "theme.uninstall.before_uninstall"
# after_uninstall = "theme.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "theme.utils.before_app_install"
# after_app_install = "theme.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "theme.utils.before_app_uninstall"
# after_app_uninstall = "theme.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "theme.notifications.get_notification_config"

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

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"theme.tasks.all"
# 	],
# 	"daily": [
# 		"theme.tasks.daily"
# 	],
# 	"hourly": [
# 		"theme.tasks.hourly"
# 	],
# 	"weekly": [
# 		"theme.tasks.weekly"
# 	],
# 	"monthly": [
# 		"theme.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "theme.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "theme.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "theme.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["theme.utils.before_request"]
# after_request = ["theme.utils.after_request"]

# Job Events
# ----------
# before_job = ["theme.utils.before_job"]
# after_job = ["theme.utils.after_job"]

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
# 	"theme.auth.validate"
# ]

# Boot session
# ------------
# Inject active theme into bootinfo so first paint is themed without a round-trip.
boot_session = "theme.api.extend_boot_session"

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

