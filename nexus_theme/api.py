import json

import frappe
from frappe import _

from nexus_theme.utils import sound_url
from nexus_theme.utils.density import MODES, label_for, normalize_density, resolve_density


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


# Overrides belong to the theme they were tuned on. With automatic light/dark
# pairing there are two themes, so there are two sets: `overrides_json`
# holds the ones for `active_theme` (the light half) as flat keys — every
# existing reader keeps working — and the dark half's under this one
# reserved key. It can never collide with a real override, because
# sanitize_overrides() only lets Theme Definition field names through. The
# key itself lives in css_safety, next to the blob sanitizer that has to
# know about it.
from nexus_theme.utils.css_safety import DARK_OVERRIDES_KEY


def _split_overrides(pref) -> tuple[dict, dict]:
	"""The (light, dark) override dicts stored on a preference row."""
	try:
		raw = json.loads(pref.overrides_json or "{}")
	except Exception:
		raw = {}
	if not isinstance(raw, dict):
		raw = {}
	dark = raw.pop(DARK_OVERRIDES_KEY, None)
	return raw, (dark if isinstance(dark, dict) else {})


def _store_overrides(pref, light: dict, dark: dict | None) -> None:
	blob = dict(light or {})
	if dark:
		blob[DARK_OVERRIDES_KEY] = dark
	pref.overrides_json = json.dumps(blob)


def _is_pairing(pref) -> bool:
	"""True while the row holds a usable light/dark pair."""
	return bool(
		pref
		and not pref.use_frappe_theme
		and pref.active_theme
		and pref.get("theme_mode") == "Automatic"
		and pref.get("dark_theme")
	)


@frappe.whitelist()
def get_active_theme():
	"""Return the user's active theme, or a null theme if they have none.

	Three states, and the middle one is the easy one to lose: no row means
	"never chose" and gets the site default; a row with `use_frappe_theme`
	means "chose Frappe's own theme" and gets nothing of ours, site default
	included; a row with a theme gets that theme.

	With pairing on, `overrides` are the light half's and `dark_overrides`
	the dark half's; the client lays each set over its own theme only.

	A user with no `User Theme Preference` row has not opted in to Theme
	Studio — the client clears our CSS variables and Frappe's native palette
	renders. We must NOT create a preference here: this runs on every
	`boot_session`, so auto-assigning a theme would both force one on every
	new user and silently undo `clear_active_theme()` on the next page load.

	`density` rides along in every answer. It is independent of the theme:
	a row may hold a density and no theme at all (set_density before any
	theme was picked, or the theme was deleted since), and that row reads
	as "never chose" for the theme while still answering for the density.
	"""
	user = frappe.session.user
	pref_name = frappe.db.exists("User Theme Preference", {"user": user})
	pref = frappe.get_doc("User Theme Preference", pref_name) if pref_name else None
	density = _resolve_density(pref)[0]
	if not pref or (not pref.use_frappe_theme and not pref.active_theme):
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
					"dark_overrides": {},
					"mode": "Single",
					"source": "site_default",
					"density": density,
				}
		return {
			"theme": None,
			"overrides": {},
			"dark_theme": None,
			"dark_overrides": {},
			"mode": "Single",
			"density": density,
		}

	if pref.use_frappe_theme:
		# A recorded opt-out, not an absence. It must NOT fall through to the
		# site default above, or picking "Frappe Light" would bring that
		# default straight back on the next reload.
		return {
			"theme": None,
			"overrides": {},
			"dark_theme": None,
			"dark_overrides": {},
			"mode": "Single",
			"source": "frappe",
			"density": density,
		}

	theme = frappe.db.get_value("Theme Definition", pref.active_theme, THEME_FIELDS, as_dict=True)
	overrides, dark_overrides = _split_overrides(pref)

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
		dark_overrides = {}

	return {
		"theme": theme,
		"overrides": overrides,
		"dark_theme": dark_theme,
		"dark_overrides": dark_overrides,
		"mode": mode,
		"source": "user",
		"density": density,
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

	if mode == "Automatic" and (not pref or not pref.active_theme):
		# No row, or an opt-out row — either way there is no light half to pair.
		# This only blocks turning pairing ON: someone on Frappe's own look must
		# still be able to turn it off, which is what "Single" means.
		frappe.throw(_("Pick a theme before enabling automatic switching"))

	if not pref:
		# Nothing is stored, and "nothing stored" already means Single. Saying
		# so is the honest answer; creating a row to record a default would
		# leave a preference the person never expressed.
		return {"ok": True, "mode": mode}

	# The dark half's overrides were tuned on the dark theme they were saved
	# with. A different dark theme, or no dark theme at all, leaves them with
	# nothing to belong to — same rule as the Studio, which clears the editor
	# when a different theme is selected.
	light, dark = _split_overrides(pref)
	if mode != "Automatic" or dark_theme != pref.dark_theme:
		dark = {}

	pref.theme_mode = mode
	pref.dark_theme = dark_theme if mode == "Automatic" else None
	_store_overrides(pref, light, dark)
	pref.save(ignore_permissions=False)
	_invalidate_bootinfo(user)
	return {"ok": True, "mode": mode}


@frappe.whitelist()
def set_active_theme(theme_name: str, overrides=None):
	"""Apply a theme, with optional per-user overrides on top of it.

	With automatic light/dark pairing on, the theme replaces the half of
	the pair that matches its own polarity: a dark theme becomes the dark
	half, a light one the light half, and the other half is left alone.
	Overrides go to the same half. This used to always overwrite the light
	half, so applying a theme while the OS was in dark mode changed nothing
	on screen, and applying a dark one while the pair was showing it stored
	that dark theme as the light half too.

	Returns which half was written so the client can say so when it is not
	the one showing.
	"""
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
		light, dark = _split_overrides(pref)
	else:
		pref = frappe.new_doc("User Theme Preference")
		pref.user = user
		light, dark = {}, {}

	pairing = _is_pairing(pref)
	half = "light"
	if pairing and frappe.db.get_value("Theme Definition", theme_name, "is_dark"):
		half = "dark"

	if half == "dark":
		pref.dark_theme = theme_name
		dark = overrides
	else:
		pref.active_theme = theme_name
		light = overrides
		if not pairing:
			# Single mode has no dark half, so nothing for these to belong to.
			dark = {}

	# Applying a theme ends any opt-out to Frappe's own theme.
	pref.use_frappe_theme = 0
	_store_overrides(pref, light, dark)
	pref.save(ignore_permissions=False)
	_invalidate_bootinfo(user)
	return {"ok": True, "half": half, "mode": "Automatic" if pairing else "Single"}


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


def _unique_own_theme_name(theme_name: str, user: str | None = None) -> str:
	"""A theme_name none of this user's own themes holds yet.

	Names only need to be distinct within one person's gallery, so the
	suffix is chosen against their themes alone: importing "Brand" while a
	"Brand" of yours exists gives "Brand (2)" and leaves the original be.
	"""
	user = user or frappe.session.user
	base = str(theme_name)[:140]
	name, suffix = base, 2
	while frappe.db.exists("Theme Definition", {"owner_user": user, "is_default": 0, "theme_name": name}):
		name = f"{base} ({suffix})"
		suffix += 1
	return name


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
		# theme_name is no longer unique across the site — two people may
		# each have a "My Theme", and "Dracula" may be someone's own take on
		# the bundled one — but one person's themes still need distinct
		# names, or the gallery shows two cards nobody can tell apart. Only
		# a rename can clash: a new theme under a taken name matched above.
		clash = frappe.db.exists(
			"Theme Definition", dict(own, theme_name=payload["theme_name"], name=["!=", existing])
		)
		if clash:
			frappe.throw(_("You already have a theme called {0}.").format(payload["theme_name"]))
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

	A row that also carries a density is not dropped, only emptied of the
	theme: the density is the person's own choice and has nothing to do
	with the theme that is going. A row with nothing else on it goes.
	"""
	rows = frappe.get_all(
		"User Theme Preference",
		filters={"active_theme": theme_name},
		fields=["name", "user", "density"],
	)
	using = [r.user for r in rows]
	keep = [r.name for r in rows if normalize_density(r.density)]
	drop = [r.name for r in rows if r.name not in keep]
	if drop:
		frappe.db.delete("User Theme Preference", {"name": ["in", drop]})
	if keep:
		frappe.db.set_value(
			"User Theme Preference",
			{"name": ["in", keep]},
			{"active_theme": None, "dark_theme": None, "theme_mode": "Single", "overrides_json": "{}"},
			update_modified=False,
		)

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

	# An import is always a new theme. save_custom_theme() updates in place
	# when either the key or the name matches one of the user's own themes,
	# and a fresh key alone was not enough: an export of "Brand" imported
	# back onto the site that has "Brand" got a new key, matched on the name,
	# and quietly overwrote the original. Both are made unique first.
	clean["theme_key"] = _unique_theme_key(clean["theme_key"])
	clean["theme_name"] = _unique_own_theme_name(clean["theme_name"])

	return save_custom_theme(clean, share_public=share_public)


# ---------------------------------------------------------------------------
# Density
# ---------------------------------------------------------------------------
# How much vertical room the Desk gives rows, fields and buttons: Compact,
# Comfortable (Frappe's own spacing) or Spacious. Stored on the same row as
# the theme but independent of it — see utils/density.py for the modes and
# the resolution order (user, then the site's default, then Comfortable).


def _resolve_density(pref=None) -> tuple[str, str]:
	"""(key, source) for the session user, given their preference row if
	it is already loaded. Reads the row off the document rather than the
	table, so a boot on a site whose migrate has not added the column yet
	still answers (with the site's default) instead of failing."""
	user_value = pref.get("density") if pref else None
	return resolve_density(user_value, _settings()["default_density"])


@frappe.whitelist()
def get_density():
	"""The density this user's Desk should draw at: {density, source}.

	`density` is a mode key ("compact"); `source` is which layer answered —
	"user", "site_default" or "default".
	"""
	user = frappe.session.user
	pref_name = frappe.db.exists("User Theme Preference", {"user": user})
	pref = frappe.get_doc("User Theme Preference", pref_name) if pref_name else None
	key, source = _resolve_density(pref)
	return {"density": key, "source": source}


@frappe.whitelist()
def set_density(density: str | None = None):
	"""Store this user's density. Empty means "follow the site default".

	Takes a key or a label, in any case. No theme is needed and none is
	touched: the row is created with only a density when the person has
	never picked a theme, and a row that opted out to Frappe's own theme
	keeps that opt-out. Clearing the density on a row that holds nothing
	else removes the row, which reads the same as never having chosen.
	"""
	key = normalize_density(density)
	if density not in (None, "") and not key:
		frappe.throw(
			_("{0} is not a density. Choose {1}.").format(density, ", ".join(m["label"] for m in MODES))
		)

	user = frappe.session.user
	pref_name = frappe.db.exists("User Theme Preference", {"user": user})
	if pref_name:
		pref = frappe.get_doc("User Theme Preference", pref_name)
	elif key:
		pref = frappe.new_doc("User Theme Preference")
		pref.user = user
	else:
		# Nothing stored already means "follow the site". Creating a row to
		# record that would leave a preference the person never expressed.
		resolved, source = _resolve_density(None)
		return {"ok": True, "density": resolved, "source": source}

	if not key and not pref.use_frappe_theme and not pref.active_theme:
		# The density was the only thing on the row; without it the row is
		# empty, which validate() rightly refuses. Emptiness is "never chose".
		frappe.delete_doc("User Theme Preference", pref.name, ignore_permissions=False)
		_invalidate_bootinfo(user)
		resolved, source = _resolve_density(None)
		return {"ok": True, "density": resolved, "source": source}

	pref.density = label_for(key) if key else None
	pref.save(ignore_permissions=False)
	_invalidate_bootinfo(user)
	resolved, source = _resolve_density(pref)
	return {"ok": True, "density": resolved, "source": source}


def extend_boot_session(bootinfo):
	"""Inject active theme and sound map into bootinfo so first paint is themed."""
	try:
		bootinfo["active_theme"] = get_active_theme()
	except Exception:
		frappe.log_error(title="theme: boot_session active_theme failed")
	try:
		# Also present inside active_theme; kept apart so the density still
		# reaches the Desk when the theme lookup fails, and so the client can
		# find it without knowing anything about themes.
		bootinfo["nexus_density"] = get_density()
	except Exception:
		frappe.log_error(title="theme: boot_session density failed")
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
	try:
		from nexus_theme.whats_new import boot_payload

		bootinfo["nexus_theme_whats_new"] = boot_payload()
	except Exception:
		frappe.log_error(title="theme: boot_session whats_new failed")


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
	"""The user's preference row, locked for this transaction.

	for_update makes a second request for the same user wait on the first
	instead of both loading the same `modified` and the loser failing with
	TimestampMismatchError on save. The first-ever save has no row to lock,
	so two of them can both try to insert; the one that loses the unique
	race rolls back to its savepoint and reads the winner's row.
	"""
	user = user or frappe.session.user
	name = frappe.db.exists("User Sound Preference", {"user": user})
	if name:
		return frappe.get_doc("User Sound Preference", name, for_update=True)
	doc = frappe.new_doc("User Sound Preference")
	doc.user = user
	doc.enabled = 1
	frappe.db.savepoint("sound_pref_insert")
	try:
		doc.insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		frappe.db.rollback(save_point="sound_pref_insert")
		name = frappe.db.exists("User Sound Preference", {"user": user})
		if not name:
			raise
		return frappe.get_doc("User Sound Preference", name, for_update=True)
	return doc


# The URL rule itself lives in utils/sound_url.py, which has no frappe
# import and is covered by the pure tests; these names stay for callers.
SOUND_EXTENSIONS = sound_url.SOUND_EXTENSIONS
_SOUND_URL_RE = sound_url.SOUND_URL_RE


def _assert_sound_url(file_url: str) -> None:
	"""Refuse anything that is not a sound file on this site.

	The value becomes an <audio src> in the user's Desk on every event, so an
	arbitrary URL is a stored outbound beacon to a third-party host, and a
	scheme such as javascript: has no business anywhere near a src attribute.
	Only checked here — the row's Attach field would accept any string.

	An empty value passes: a row may carry only a volume, for an event that
	keeps Frappe's stock sound (see set_user_sound).
	"""
	url = (file_url or "").strip()
	if not url:
		return
	if not sound_url.is_sound_url(url):
		frappe.throw(_("That is not a sound file on this site."))


def _discard_rejected_upload(file_url: str) -> None:
	"""Delete the File record behind a URL that set_user_sound has refused.

	Sound Studio uploads first and asks to use the file second, so a refusal
	would otherwise leave an orphan attached to the preference row. Only a
	File this user uploaded against their own preference row qualifies —
	the caller must not be able to delete anyone else's attachments by
	naming their URL.

	The delete is committed before the caller throws, because the throw
	rolls the request's transaction back; nothing else has been written
	at this point.
	"""
	url = (file_url or "").strip()
	if not url.startswith(("/files/", "/private/files/")):
		return
	name = frappe.db.get_value(
		"File",
		{
			"file_url": url,
			"owner": frappe.session.user,
			"attached_to_doctype": "User Sound Preference",
			"attached_to_name": frappe.session.user,
		},
		"name",
	)
	if not name:
		return
	frappe.delete_doc("File", name, ignore_permissions=True, force=True)
	frappe.db.commit()


def _assert_sounds_allowed() -> None:
	"""get_user_sounds() already reports sounds as off when the site turns
	them off; the writes have to refuse too, or the switch is cosmetic."""
	if not _settings()["allow_user_sounds"]:
		frappe.throw(_("Custom sounds are turned off on this site."))


@frappe.whitelist()
def get_user_sounds():
	"""Return this user's sound configuration.

	{enabled, allowed, login_stamp, mapping: {event: {url, volume}}}

	`enabled` is the user's own switch and mutes everything, stock sounds
	included. `allowed` is the site's "Allow User Sounds" setting: off means
	no custom files are handed out and Sound Studio cannot write, but
	Frappe's own sounds keep playing — the site turned off customisation,
	not audio. A mapping entry may have no url, when the user only set a
	volume for an event that keeps its stock sound.

	`login_stamp` is the user's last_login. The Desk plays the login sound
	when it sees a stamp it has not played for, which is once per sign-in
	rather than once per page load or tab.
	"""
	user = frappe.session.user
	login_stamp = frappe.db.get_value("User", user, "last_login")
	payload = {
		"enabled": 1,
		"allowed": 1,
		"login_stamp": str(login_stamp) if login_stamp else None,
		"mapping": {},
	}
	if not _settings()["allow_user_sounds"]:
		payload["allowed"] = 0
		return payload

	name = frappe.db.exists("User Sound Preference", {"user": user})
	if not name:
		return payload
	pref = frappe.get_doc("User Sound Preference", name)
	for row in pref.sounds or []:
		if not row.event_key:
			continue
		payload["mapping"][row.event_key] = {
			"url": row.file or None,
			"volume": float(row.volume) if row.volume is not None else 0.5,
		}
	payload["enabled"] = 1 if pref.enabled else 0
	return payload


@frappe.whitelist()
def set_user_sound(event_key: str, file_url: str | None = None, volume: float | str | None = 0.5):
	"""Store a file and/or a volume for one event.

	Without a file the volume alone is stored, against the existing file if
	the event has one and otherwise on its own — the volume then applies to
	Frappe's stock sound for that event.
	"""
	_assert_sounds_allowed()
	file_url = (file_url or "").strip()
	if event_key not in SOUND_EVENTS:
		_discard_rejected_upload(file_url)
		frappe.throw(_("Unknown sound event: {0}").format(event_key))
	try:
		_assert_sound_url(file_url)
	except frappe.ValidationError:
		_discard_rejected_upload(file_url)
		raise
	try:
		vol = float(volume) if volume is not None else 0.5
	except (TypeError, ValueError):
		vol = 0.5
	vol = max(0.0, min(1.0, vol))

	# The row is locked for update, so a save that still sees a stale
	# `modified` (the lock was taken after the other request committed, on
	# a database that does not honour it) is retried on a fresh read.
	for attempt in range(3):
		pref = _get_or_create_sound_pref()
		existing = None
		for row in pref.sounds or []:
			if row.event_key == event_key:
				existing = row
				break
		if existing:
			if file_url:
				existing.file = file_url
			existing.volume = vol
		else:
			pref.append("sounds", {"event_key": event_key, "file": file_url or None, "volume": vol})
		try:
			pref.save(ignore_permissions=False)
			break
		except frappe.TimestampMismatchError:
			if attempt == 2:
				raise
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


@frappe.whitelist()
def get_login_preview():
	"""The sign-in screen's brand and words, for Theme Studio's preview.

	Every value here is already shown to anonymous visitors on the login page,
	so this adds no exposure; it saves a Desk user from signing out to see
	what their theme does to the sign-in screen.
	"""
	from nexus_theme.login_page import preview_payload

	return preview_payload()


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
