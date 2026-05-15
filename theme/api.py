import json
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


@frappe.whitelist()
def get_available_themes():
	user = frappe.session.user
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
	public = frappe.get_all(
		"Theme Definition",
		filters={"is_public": 1, "is_default": 0, "owner_user": ["!=", user]},
		fields=THEME_FIELDS,
		order_by="modified desc",
	)
	return {"defaults": defaults, "owned": owned, "public": public}


@frappe.whitelist()
def get_active_theme():
	user = frappe.session.user
	pref_name = frappe.db.exists("User Theme Preference", {"user": user})
	if not pref_name:
		# No preference set — signal the client to render stock Frappe UI.
		return {"theme": None, "overrides": {}}

	pref = frappe.get_doc("User Theme Preference", pref_name)
	theme = frappe.db.get_value(
		"Theme Definition", pref.active_theme, THEME_FIELDS, as_dict=True
	)
	try:
		overrides = json.loads(pref.overrides_json or "{}")
	except Exception:
		overrides = {}
	return {"theme": theme, "overrides": overrides}


@frappe.whitelist()
def set_active_theme(theme_name: str, overrides=None):
	if not theme_name:
		frappe.throw(_("theme_name is required"))
	if not frappe.db.exists("Theme Definition", theme_name):
		frappe.throw(_("Theme {0} does not exist").format(theme_name))

	if isinstance(overrides, str):
		try:
			overrides = json.loads(overrides or "{}")
		except Exception:
			overrides = {}
	overrides = overrides or {}

	user = frappe.session.user
	pref_name = frappe.db.exists("User Theme Preference", {"user": user})
	if pref_name:
		pref = frappe.get_doc("User Theme Preference", pref_name)
	else:
		pref = frappe.new_doc("User Theme Preference")
		pref.user = user

	pref.active_theme = theme_name
	pref.overrides_json = json.dumps(overrides)
	pref.save(ignore_permissions=False)
	frappe.db.commit()
	_invalidate_bootinfo(user)
	return {"ok": True}


@frappe.whitelist()
def save_custom_theme(payload, share_public=0):
	if isinstance(payload, str):
		payload = json.loads(payload)
	if not isinstance(payload, dict):
		frappe.throw(_("payload must be a JSON object"))

	required = {"theme_name", "theme_key"}
	if not required.issubset(payload):
		frappe.throw(_("theme_name and theme_key are required"))

	user = frappe.session.user
	existing = frappe.db.exists(
		"Theme Definition",
		{"theme_key": payload["theme_key"], "owner_user": user, "is_default": 0},
	)

	if existing:
		doc = frappe.get_doc("Theme Definition", existing)
	else:
		doc = frappe.new_doc("Theme Definition")
		doc.is_default = 0
		doc.owner_user = user

	protected = {"name", "is_default", "owner_user", "doctype"}
	for field in THEME_FIELDS:
		if field in protected:
			continue
		if field in payload and payload[field] not in (None, ""):
			setattr(doc, field, payload[field])

	doc.theme_key = payload["theme_key"]
	doc.theme_name = payload["theme_name"]
	doc.is_public = 1 if int(share_public or 0) else 0
	doc.save(ignore_permissions=False)
	frappe.db.commit()
	_invalidate_bootinfo(user)
	return {"name": doc.name}


@frappe.whitelist()
def clear_active_theme():
	"""Remove the current user's theme preference so Frappe's native UI is restored."""
	user = frappe.session.user
	pref_name = frappe.db.exists("User Theme Preference", {"user": user})
	if pref_name:
		frappe.delete_doc("User Theme Preference", pref_name, ignore_permissions=False)
		frappe.db.commit()
	_invalidate_bootinfo(user)
	return {"ok": True}


@frappe.whitelist()
def get_recommended_palettes():
	"""Return the curated palette list for the Theme Studio "Palettes" tab.

	Each palette is a complete WCAG-AA-validated color set that the editor
	applies through the same previewOverrides flow as the manual pickers.
	Importing inside the function keeps `bench start` fast — palettes only
	load when a user actually opens the Theme Studio."""
	from theme.utils.palettes import get_palettes
	return get_palettes()


@frappe.whitelist()
def delete_custom_theme(theme_name: str):
	if not theme_name:
		frappe.throw(_("theme_name is required"))
	doc = frappe.get_doc("Theme Definition", theme_name)
	if doc.is_default:
		frappe.throw(_("Default themes cannot be deleted"))
	if doc.owner_user != frappe.session.user:
		frappe.throw(_("You can only delete your own themes"))
	frappe.delete_doc("Theme Definition", theme_name)
	frappe.db.commit()
	return {"ok": True}


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


@frappe.whitelist()
def get_user_sounds():
	"""Return this user's sound configuration: {enabled, mapping: {event: {url, volume}}}."""
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
	if event_key not in SOUND_EVENTS:
		frappe.throw(_("Unknown sound event: {0}").format(event_key))
	if not file_url:
		frappe.throw(_("file_url is required"))
	try:
		vol = float(volume) if volume is not None else 0.5
	except (TypeError, ValueError):
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
	frappe.db.commit()
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
	frappe.db.commit()
	_invalidate_bootinfo()
	return {"ok": True, "event_key": event_key}


@frappe.whitelist()
def toggle_user_sounds(enabled):
	pref = _get_or_create_sound_pref()
	pref.enabled = 1 if int(enabled or 0) else 0
	pref.save(ignore_permissions=False)
	frappe.db.commit()
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
	frappe.db.commit()
	_invalidate_bootinfo()
	return {"ok": True}
