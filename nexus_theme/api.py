import json
import re

import frappe
from frappe import _


def _invalidate_bootinfo(user: str | None = None) -> None:
	"""Drop the per-user bootinfo cache so the next page load reads the fresh
	theme preference. Without this, Frappe serves the stale cached bootinfo
	on refresh and the just-saved theme reverts to the previous one."""
	user = user or frappe.session.user
	try:
		frappe.cache.hdel("bootinfo", user)
	except Exception:
		# Older Frappe versions exposed `frappe.cache()` as a callable.
		try:
			frappe.cache().hdel("bootinfo", user)
		except Exception:
			frappe.log_error(title="theme: failed to invalidate bootinfo cache")


THEME_FIELDS = [
	"name",
	"theme_name",
	"theme_key",
	"is_dark",
	"bg_primary",
	"bg_surface",
	"bg_input",
	"text_primary",
	"text_muted",
	"accent",
	"accent_hover",
	"button_bg",
	"button_text",
	"button_hover_bg",
	"border",
	"font_family",
	"font_size_base",
	"font_weight_base",
	"transition_duration",
	"enable_hover_lift",
	"border_radius",
]


def _settings():
	from nexus_theme.nexus_theme.doctype.theme_settings.theme_settings import (
		get_settings,
	)

	return get_settings()


def _visible_to_user(theme_names: list[str], user: str | None = None) -> set[str]:
	"""Of `theme_names`, the ones this user's roles allow.

	A theme with no `restrict_to_roles` rows is visible to everyone; one with
	rows is visible only to holders of at least one listed role. Resolved in
	a single query rather than per-theme so the gallery stays one round-trip.
	"""
	if not theme_names:
		return set()
	rows = frappe.get_all(
		"Theme Role",
		filters={"parenttype": "Theme Definition", "parent": ["in", theme_names]},
		fields=["parent", "role"],
	)
	if not rows:
		return set(theme_names)

	restricted: dict[str, set[str]] = {}
	for row in rows:
		restricted.setdefault(row.parent, set()).add(row.role)

	user_roles = set(frappe.get_roles(user or frappe.session.user))
	return {name for name in theme_names if name not in restricted or (restricted[name] & user_roles)}


def _apply_visibility(themes: list[dict], user: str | None = None) -> list[dict]:
	allowed = _visible_to_user([t["name"] for t in themes], user)
	return [t for t in themes if t["name"] in allowed]


def _assert_theme_applicable(theme_name: str, user: str | None = None) -> None:
	"""Refuse a theme the caller is not offered.

	get_available_themes() filters the gallery, but set_active_theme() and
	set_theme_mode() take a bare name and only checked that it existed — so a
	call from the console could apply another user's private theme, one
	hidden from the caller's roles, or one an admin had struck off the
	allow-list. Same rules as the gallery, enforced at the point of use.
	"""
	user = user or frappe.session.user
	row = frappe.db.get_value(
		"Theme Definition",
		theme_name,
		["is_default", "is_public", "owner_user"],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Theme {0} does not exist").format(theme_name))
	if not (row.is_default or row.is_public or row.owner_user == user):
		frappe.throw(_("You do not have access to theme {0}").format(theme_name))
	if theme_name not in _visible_to_user([theme_name], user):
		frappe.throw(_("Theme {0} is not available to your roles").format(theme_name))
	settings = _settings()
	if settings["restrict_theme_choice"] and theme_name not in set(settings["allowed_themes"] or []):
		frappe.throw(_("Theme {0} is not on this site's allowed list").format(theme_name))


@frappe.whitelist()
def get_available_themes():
	user = frappe.session.user
	settings = _settings()

	defaults = frappe.get_all(
		"Theme Definition",
		filters={"is_default": 1},
		fields=THEME_FIELDS,
		order_by="theme_name asc",
	)
	owned = frappe.get_all(
		"Theme Definition",
		filters={"owner_user": user, "is_default": 0},
		fields=THEME_FIELDS,
		order_by="modified desc",
	)
	# `owner_user != user` is evaluated in Python rather than SQL: in SQL
	# `NULL != 'x'` is NULL, not TRUE, so a public theme with no owner would
	# be silently dropped from the gallery.
	public = [
		t
		for t in frappe.get_all(
			"Theme Definition",
			filters={"is_public": 1, "is_default": 0},
			fields=THEME_FIELDS,
			order_by="modified desc",
		)
		if t.get("owner_user") != user
	]

	defaults = _apply_visibility(defaults, user)
	public = _apply_visibility(public, user)

	# An admin restricting the theme list only narrows what is on offer. A
	# theme a user already has stays applied — silently reverting someone's
	# Desk because an allow-list changed would be worse than showing them a
	# theme that is no longer offered.
	if settings["restrict_theme_choice"]:
		allowed = set(settings["allowed_themes"] or [])
		defaults = [t for t in defaults if t["name"] in allowed]
		public = [t for t in public if t["name"] in allowed]
		owned = [t for t in owned if t["name"] in allowed]

	return {
		"defaults": defaults,
		"owned": owned,
		"public": public,
		"settings": {
			"allow_custom_themes": 1 if settings["allow_custom_themes"] else 0,
			"allow_public_sharing": 1 if settings["allow_public_sharing"] else 0,
		},
	}


@frappe.whitelist()
def get_active_theme():
	"""Return the user's active theme, or a null theme if they have none.

	Three states, and the middle one is the easy one to lose: no row means
	"never chose" and gets the site default; a row with `use_frappe_theme`
	means "chose Frappe's own theme" and gets nothing of ours, site default
	included; a row with a theme gets that theme.

	A user with no `User Theme Preference` row has not opted in to Theme
	Studio — the client clears our CSS variables and Frappe's native palette
	renders. We must NOT create a preference here: this runs on every
	`boot_session`, so auto-assigning a theme would both force one on every
	new user and silently undo `clear_active_theme()` on the next page load.
	"""
	user = frappe.session.user
	pref_name = frappe.db.exists("User Theme Preference", {"user": user})
	if not pref_name:
		# No preference of their own — fall back to the site default if an
		# admin set one. Still no row is created: this runs on every boot,
		# and writing here would both pin the user to today's default and
		# undo clear_active_theme() on the next page load.
		default_name = _settings()["site_default_theme"]
		if default_name:
			theme = frappe.db.get_value("Theme Definition", default_name, THEME_FIELDS, as_dict=True)
			if theme:
				return {
					"theme": theme,
					"overrides": {},
					"dark_theme": None,
					"mode": "Single",
					"source": "site_default",
				}
		return {"theme": None, "overrides": {}, "dark_theme": None, "mode": "Single"}

	pref = frappe.get_doc("User Theme Preference", pref_name)
	if pref.use_frappe_theme:
		# A recorded opt-out, not an absence. It must NOT fall through to the
		# site default above, or picking "Frappe Light" would bring that
		# default straight back on the next reload.
		return {
			"theme": None,
			"overrides": {},
			"dark_theme": None,
			"mode": "Single",
			"source": "frappe",
		}

	theme = frappe.db.get_value("Theme Definition", pref.active_theme, THEME_FIELDS, as_dict=True)
	try:
		overrides = json.loads(pref.overrides_json or "{}")
	except Exception:
		overrides = {}

	# `theme` and `overrides` keep their original meaning so existing callers
	# are unaffected; automatic pairing is additive.
	mode = pref.get("theme_mode") or "Single"
	dark_theme = None
	if mode == "Automatic" and pref.get("dark_theme"):
		dark_theme = frappe.db.get_value("Theme Definition", pref.dark_theme, THEME_FIELDS, as_dict=True)
	if not dark_theme:
		# A mode of Automatic with no usable dark theme behaves as Single
		# rather than leaving the client to guess.
		mode = "Single"

	return {
		"theme": theme,
		"overrides": overrides,
		"dark_theme": dark_theme,
		"mode": mode,
		"source": "user",
	}


@frappe.whitelist()
def set_theme_mode(mode: str, dark_theme: str | None = None):
	"""Switch between a single theme and an automatic light/dark pair."""
	if mode not in ("Single", "Automatic"):
		frappe.throw(_("mode must be Single or Automatic"))
	if mode == "Automatic":
		if not dark_theme:
			frappe.throw(_("Pick a dark theme to pair with"))
		_assert_theme_applicable(dark_theme)

	user = frappe.session.user
	pref_name = frappe.db.exists("User Theme Preference", {"user": user})
	pref = frappe.get_doc("User Theme Preference", pref_name) if pref_name else None
	if not pref or not pref.active_theme:
		# No row, or an opt-out row — either way there is no theme to pair.
		frappe.throw(_("Pick a theme before enabling automatic switching"))

	pref.theme_mode = mode
	pref.dark_theme = dark_theme if mode == "Automatic" else None
	pref.save(ignore_permissions=False)
	_invalidate_bootinfo(user)
	return {"ok": True, "mode": mode}


@frappe.whitelist()
def set_active_theme(theme_name: str, overrides=None):
	if not theme_name:
		frappe.throw(_("theme_name is required"))
	_assert_theme_applicable(theme_name)

	if isinstance(overrides, str):
		try:
			overrides = json.loads(overrides or "{}")
		except Exception:
			overrides = {}
	# Drop any override whose value isn't a real color / CSS token before it
	# is persisted — overrides_json is injected into the DOM as CSS on boot.
	from nexus_theme.utils.css_safety import sanitize_overrides

	overrides = sanitize_overrides(overrides or {})

	user = frappe.session.user
	pref_name = frappe.db.exists("User Theme Preference", {"user": user})
	if pref_name:
		pref = frappe.get_doc("User Theme Preference", pref_name)
	else:
		pref = frappe.new_doc("User Theme Preference")
		pref.user = user

	# Applying a theme ends any opt-out to Frappe's own theme.
	pref.use_frappe_theme = 0
	pref.active_theme = theme_name
	pref.overrides_json = json.dumps(overrides)
	pref.save(ignore_permissions=False)
	_invalidate_bootinfo(user)
	return {"ok": True}


def _unique_theme_key(base_key: str) -> str:
	"""A theme_key no Theme Definition holds yet.

	theme_key is the docname, so a collision surfaces as a raw duplicate-name
	error from the database. A user naming their own theme "Dracula" collides
	with the bundled one; a suffix keeps the save working. The caller has
	already matched the user's *own* theme of that key, which is updated in
	place and never reaches here.
	"""
	base = str(base_key)[:120]
	key, suffix = base, 2
	while frappe.db.exists("Theme Definition", key):
		key = f"{base}-{suffix}"
		suffix += 1
	return key


@frappe.whitelist()
def save_custom_theme(payload, share_public=0):
	if isinstance(payload, str):
		payload = json.loads(payload)
	if not isinstance(payload, dict):
		frappe.throw(_("payload must be a JSON object"))

	required = {"theme_name", "theme_key"}
	if not required.issubset(payload):
		frappe.throw(_("theme_name and theme_key are required"))

	settings = _settings()
	if not settings["allow_custom_themes"]:
		frappe.throw(_("Custom themes are disabled on this site."))
	if not settings["allow_public_sharing"]:
		share_public = 0

	user = frappe.session.user
	# Saving under the same key *or* the same name as one of your own themes
	# updates it in place — that is what "save with the same name" means.
	own = {"owner_user": user, "is_default": 0}
	existing = frappe.db.exists(
		"Theme Definition", dict(own, theme_key=payload["theme_key"])
	) or frappe.db.exists("Theme Definition", dict(own, theme_name=payload["theme_name"]))

	theme_key = payload["theme_key"]
	if existing:
		doc = frappe.get_doc("Theme Definition", existing)
		theme_key = doc.theme_key
	else:
		theme_key = _unique_theme_key(theme_key)
		doc = frappe.new_doc("Theme Definition")
		doc.is_default = 0
		doc.owner_user = user

	protected = {"name", "is_default", "owner_user", "doctype"}
	for field in THEME_FIELDS:
		if field in protected:
			continue
		if field in payload and payload[field] not in (None, ""):
			setattr(doc, field, payload[field])

	doc.theme_key = theme_key
	doc.theme_name = payload["theme_name"]
	doc.is_public = 1 if int(share_public or 0) else 0
	doc.save(ignore_permissions=False)
	_invalidate_bootinfo(user)
	return {"name": doc.name}


@frappe.whitelist()
def clear_active_theme():
	"""Hand the Desk back to Frappe's own theme — and remember that.

	This used to delete the preference row. That is wrong whenever an admin
	has set a site default theme: no row means "never chose", so the default
	came straight back on the next page load and the user could never get
	Frappe's own theme to stick. The choice is stored as an explicit opt-out
	instead; validate() strips every other theme field off the row.
	"""
	user = frappe.session.user
	pref_name = frappe.db.exists("User Theme Preference", {"user": user})
	if pref_name:
		pref = frappe.get_doc("User Theme Preference", pref_name)
	else:
		pref = frappe.new_doc("User Theme Preference")
		pref.user = user
	pref.use_frappe_theme = 1
	pref.save(ignore_permissions=False)
	_invalidate_bootinfo(user)
	return {"ok": True}


@frappe.whitelist()
def get_recommended_palettes():
	"""Return the curated palette list for the Theme Studio "Palettes" tab.

	Each palette is a complete WCAG-AA-validated color set that the editor
	applies through the same previewOverrides flow as the manual pickers.
	Importing inside the function keeps `bench start` fast — palettes only
	load when a user actually opens the Theme Studio."""
	from nexus_theme.utils.palettes import get_palettes

	return get_palettes()


@frappe.whitelist()
def generate_palette(seed, is_dark=0):
	"""Derive full palettes from one brand colour, for the "Generate" tab.

	Returns the same shape as get_recommended_palettes() — one entry per
	variant — so the editor draws generated and curated palettes with the
	same card. Read-only: nothing is written until the user applies a result
	and saves, which goes through save_custom_theme like any manual edit.

	The seed is the only user-controlled input, and it never reaches CSS: it
	is parsed to HLS and every emitted value is a freshly formatted #rrggbb.
	It is still validated here so a typo returns a clear message instead of a
	stack trace.
	"""
	from nexus_theme.utils.palette_generator import generate_variants

	try:
		return generate_variants(seed, bool(int(is_dark or 0)))
	except ValueError:
		frappe.throw(_("{0} is not a valid hex colour.").format(seed))


@frappe.whitelist()
def delete_custom_theme(theme_name: str):
	if not theme_name:
		frappe.throw(_("theme_name is required"))
	doc = frappe.get_doc("Theme Definition", theme_name)
	if doc.is_default:
		frappe.throw(_("Default themes cannot be deleted"))
	if doc.owner_user != frappe.session.user:
		frappe.throw(_("You can only delete your own themes"))

	# Theme Settings links to themes as well, and those links are an admin's
	# choices — say where to look rather than let the generic link error out.
	settings = _settings()
	if theme_name == settings["site_default_theme"]:
		frappe.throw(
			_("{0} is the site default theme. Change that in Theme Settings first.").format(doc.theme_name)
		)
	if theme_name in set(settings["allowed_themes"] or []):
		frappe.throw(
			_("{0} is on the allowed themes list. Remove it in Theme Settings first.").format(doc.theme_name)
		)

	_detach_theme_from_preferences(theme_name)
	frappe.delete_doc("Theme Definition", theme_name)
	return {"ok": True}


def _detach_theme_from_preferences(theme_name: str) -> None:
	"""Release every User Theme Preference that points at a theme about to go.

	Saving a custom theme applies it, so the owner's own preference almost
	always links to it — and a shared theme may be in use by anyone. Left in
	place, those links fail the delete with LinkExistsError, which the UI
	showed as a bare "Failed to delete theme". Whoever had it active goes
	back to "never chose" (the site default, or Frappe's own theme); whoever
	paired it as the dark half of an automatic pair drops to a single theme.
	"""
	using = frappe.get_all("User Theme Preference", filters={"active_theme": theme_name}, pluck="user")
	if using:
		frappe.db.delete("User Theme Preference", {"active_theme": theme_name})

	pairing = frappe.get_all("User Theme Preference", filters={"dark_theme": theme_name}, pluck="user")
	if pairing:
		frappe.db.set_value(
			"User Theme Preference",
			{"dark_theme": theme_name},
			{"dark_theme": None, "theme_mode": "Single"},
			update_modified=False,
		)

	for user in set(using) | set(pairing):
		_invalidate_bootinfo(user)


# ---------------------------------------------------------------------------
# Import / export
# ---------------------------------------------------------------------------

# The portable shape of a theme. Excludes identity and ownership: an imported
# theme belongs to whoever imports it, on whatever site they import it to.
PORTABLE_FIELDS = [f for f in THEME_FIELDS if f not in ("name", "owner_user")]

EXPORT_FORMAT = "nexus_theme.theme/1"


@frappe.whitelist()
def export_theme(theme_name: str):
	"""Return one theme as a portable dict, for saving to a .json file.

	Lets a brand theme live in version control and be promoted between
	sites instead of being rebuilt by hand in the color pickers.
	"""
	if not theme_name:
		frappe.throw(_("theme_name is required"))
	doc = frappe.get_doc("Theme Definition", theme_name)
	if not (doc.is_default or doc.is_public or doc.owner_user == frappe.session.user):
		frappe.throw(_("You can only export your own themes"))

	return {
		"format": EXPORT_FORMAT,
		"exported_from": frappe.local.site,
		"theme": {f: doc.get(f) for f in PORTABLE_FIELDS},
	}


@frappe.whitelist()
def import_theme(payload, share_public=0):
	"""Create a theme from an exported payload.

	The values still go through Theme Definition's own validation, so an
	imported file cannot introduce a color the CSS guard would reject or a
	contrast pair below AA.
	"""
	if isinstance(payload, str):
		try:
			payload = json.loads(payload)
		except Exception:
			frappe.throw(_("That file is not valid JSON."))
	if not isinstance(payload, dict):
		frappe.throw(_("That file is not a theme export."))

	# Accept either the wrapper or a bare theme dict.
	theme = payload.get("theme") if "theme" in payload else payload
	if not isinstance(theme, dict) or not theme.get("theme_key"):
		frappe.throw(_("That file is not a theme export."))

	fmt = payload.get("format")
	if fmt and fmt != EXPORT_FORMAT:
		frappe.throw(_("Unsupported export format: {0}").format(fmt))

	clean = {f: theme[f] for f in PORTABLE_FIELDS if f in theme}
	clean["theme_name"] = theme.get("theme_name") or theme["theme_key"]

	# A key that already exists would silently overwrite the user's own
	# theme of that name, so give the import its own.
	base_key = str(clean["theme_key"])[:120]
	key = base_key
	suffix = 2
	while frappe.db.exists("Theme Definition", key):
		key = f"{base_key}-{suffix}"
		suffix += 1
	clean["theme_key"] = key
	if key != base_key:
		clean["theme_name"] = f"{clean['theme_name']} ({suffix - 1})"

	return save_custom_theme(clean, share_public=share_public)


def extend_boot_session(bootinfo):
	"""Inject active theme and sound map into bootinfo so first paint is themed."""
	try:
		bootinfo["active_theme"] = get_active_theme()
	except Exception:
		frappe.log_error(title="theme: boot_session active_theme failed")
	try:
		bootinfo["user_sounds"] = get_user_sounds()
	except Exception:
		frappe.log_error(title="theme: boot_session user_sounds failed")
	try:
		settings = _settings()
		bootinfo["nexus_theme_settings"] = {
			"allow_custom_themes": 1 if settings["allow_custom_themes"] else 0,
			"allow_public_sharing": 1 if settings["allow_public_sharing"] else 0,
			"allow_user_sounds": 1 if settings["allow_user_sounds"] else 0,
			"navbar_logo": settings["navbar_logo"],
			"favicon": settings["favicon"],
		}
	except Exception:
		frappe.log_error(title="theme: boot_session settings failed")


# ---------------------------------------------------------------------------
# Sound preferences
# ---------------------------------------------------------------------------

SOUND_EVENTS = {
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
}


def _get_or_create_sound_pref(user: str | None = None):
	user = user or frappe.session.user
	name = frappe.db.exists("User Sound Preference", {"user": user})
	if name:
		return frappe.get_doc("User Sound Preference", name)
	doc = frappe.new_doc("User Sound Preference")
	doc.user = user
	doc.enabled = 1
	doc.insert(ignore_permissions=True)
	return doc


# A sound this site serves: uploads land under /files or /private/files, the
# bundled presets under /assets. One path, an audio extension, nothing else.
_SOUND_URL_RE = re.compile(
	r"^/(?:assets|files|private/files)/(?:[\w .%()+-]+/)*[\w .%()+-]+"
	r"\.(?:mp3|wav|ogg|oga|m4a|aac|flac|webm|opus)$",
	re.IGNORECASE,
)


def _assert_sound_url(file_url: str) -> None:
	"""Refuse anything that is not a sound file on this site.

	The value becomes an <audio src> in the user's Desk on every event, so an
	arbitrary URL is a stored outbound beacon to a third-party host, and a
	scheme such as javascript: has no business anywhere near a src attribute.
	Only checked here — the row's Attach field would accept any string.
	"""
	url = (file_url or "").strip()
	if not _SOUND_URL_RE.match(url) or "/../" in url or "/./" in url:
		frappe.throw(_("That is not a sound file on this site."))


def _assert_sounds_allowed() -> None:
	"""get_user_sounds() already reports sounds as off when the site turns
	them off; the writes have to refuse too, or the switch is cosmetic."""
	if not _settings()["allow_user_sounds"]:
		frappe.throw(_("Custom sounds are turned off on this site."))


@frappe.whitelist()
def get_user_sounds():
	"""Return this user's sound configuration: {enabled, mapping: {event: {url, volume}}}."""
	# A site-wide off switch wins over the per-user flag.
	if not _settings()["allow_user_sounds"]:
		return {"enabled": 0, "mapping": {}}

	user = frappe.session.user
	name = frappe.db.exists("User Sound Preference", {"user": user})
	if not name:
		return {"enabled": 1, "mapping": {}}
	pref = frappe.get_doc("User Sound Preference", name)
	mapping = {}
	for row in pref.sounds or []:
		if not row.event_key or not row.file:
			continue
		mapping[row.event_key] = {
			"url": row.file,
			"volume": float(row.volume) if row.volume is not None else 0.5,
		}
	return {"enabled": 1 if pref.enabled else 0, "mapping": mapping}


@frappe.whitelist()
def set_user_sound(event_key: str, file_url: str, volume: float | str | None = 0.5):
	_assert_sounds_allowed()
	if event_key not in SOUND_EVENTS:
		frappe.throw(_("Unknown sound event: {0}").format(event_key))
	if not file_url:
		frappe.throw(_("file_url is required"))
	_assert_sound_url(file_url)
	try:
		vol = float(volume) if volume is not None else 0.5
	except TypeError, ValueError:
		vol = 0.5
	vol = max(0.0, min(1.0, vol))

	pref = _get_or_create_sound_pref()

	existing = None
	for row in pref.sounds or []:
		if row.event_key == event_key:
			existing = row
			break
	if existing:
		existing.file = file_url
		existing.volume = vol
	else:
		pref.append("sounds", {"event_key": event_key, "file": file_url, "volume": vol})
	pref.save(ignore_permissions=False)
	_invalidate_bootinfo()
	return {"ok": True, "event_key": event_key}


@frappe.whitelist()
def clear_user_sound(event_key: str):
	if event_key not in SOUND_EVENTS:
		frappe.throw(_("Unknown sound event: {0}").format(event_key))
	user = frappe.session.user
	name = frappe.db.exists("User Sound Preference", {"user": user})
	if not name:
		return {"ok": True}
	pref = frappe.get_doc("User Sound Preference", name)
	pref.sounds = [r for r in (pref.sounds or []) if r.event_key != event_key]
	pref.save(ignore_permissions=False)
	_invalidate_bootinfo()
	return {"ok": True, "event_key": event_key}


@frappe.whitelist()
def toggle_user_sounds(enabled):
	_assert_sounds_allowed()
	pref = _get_or_create_sound_pref()
	pref.enabled = 1 if int(enabled or 0) else 0
	pref.save(ignore_permissions=False)
	_invalidate_bootinfo()
	return {"ok": True, "enabled": pref.enabled}


@frappe.whitelist()
def clear_all_user_sounds():
	"""Remove every custom sound and reset to defaults."""
	user = frappe.session.user
	name = frappe.db.exists("User Sound Preference", {"user": user})
	if not name:
		return {"ok": True}
	pref = frappe.get_doc("User Sound Preference", name)
	pref.sounds = []
	pref.save(ignore_permissions=False)
	_invalidate_bootinfo()
	return {"ok": True}


def check_app_permission() -> bool:
	"""Gate the app's tile on the Desk apps screen.

	Frappe calls this from `add_to_apps_screen`; returning False hides the
	tile. Every Desk user gets the "Theme User" role on install and on
	user creation (see install.py), so in practice this shows the tile to
	anyone who can actually personalize their theme, and hides it from
	Website-only users who cannot.
	"""
	if frappe.session.user == "Administrator":
		return True
	roles = frappe.get_roles()
	return "Theme User" in roles or "System Manager" in roles
