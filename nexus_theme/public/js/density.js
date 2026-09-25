(function () {
	"use strict";

	// Density is how much vertical room the Desk gives each row, field and
	// button. Three modes: Compact, Comfortable and Spacious. Comfortable is
	// Frappe's own spacing and sets nothing at all — density.bundle.css
	// keys every rule off `html[data-density="compact"]` or
	// `html[data-density="spacious"]`, so a Desk that never hears of this
	// file is pixel-identical to one on Comfortable.
	//
	// Independent of the theme on purpose: the attribute is not scoped
	// under data-app-theme, and someone on Frappe's stock look can still be
	// Compact. ThemeManager is never consulted here.
	//
	// The cache is per user (the payload carries `user`) and is read the
	// moment this script is evaluated, before the Desk has drawn anything,
	// so a reload paints at the right density straight away rather than
	// jumping once the server is heard from. `frappe.boot` is set inline in
	// desk.html ahead of every app bundle, so on a normal load it is the
	// boot value that is applied here, and the cache only matters when boot
	// arrived without one (a stale boot cached before this feature).
	const STORAGE_KEY = "density:active";
	const ATTR = "data-density";
	const DEFAULT = "comfortable";
	const EVENT = "nexus-density-change";
	const ROOT = document.documentElement;

	// Same list, same order, as utils/density.py MODES — keep the two the same.
	const MODES = [
		{
			key: "compact",
			label: "Compact",
			description: "Tighter rows and fields, so more fits on screen.",
		},
		{
			key: "comfortable",
			label: "Comfortable",
			description: "Frappe's own spacing.",
		},
		{
			key: "spacious",
			label: "Spacious",
			description: "More room around rows and fields.",
		},
	];
	const KEYS = MODES.map((m) => m.key);

	/** Who the Desk is signed in as; null outside a booted Desk. */
	function bootUser() {
		const f = window.frappe;
		if (!f) return null;
		if (f.boot && f.boot.user && f.boot.user.name) return f.boot.user.name;
		return (f.session && f.session.user) || null;
	}

	/** The mode key for `value` (key or label, any case), or null. */
	function normalize(value) {
		if (value == null) return null;
		const text = String(value).trim().toLowerCase();
		return KEYS.indexOf(text) >= 0 ? text : null;
	}

	/** Labels are translated where the Desk can, keys never are. */
	function modes() {
		const t = window.__ || ((s) => s);
		return MODES.map((m) => ({ key: m.key, label: t(m.label), description: t(m.description) }));
	}

	/** What the page is drawn at right now. */
	function get() {
		return normalize(ROOT.getAttribute(ATTR)) || DEFAULT;
	}

	/**
	 * Set the attribute, locally only. Comfortable removes it, so the
	 * default state is the absence of anything rather than a value CSS
	 * has to match. Returns the key that is now showing.
	 */
	function apply(key) {
		const next = normalize(key) || DEFAULT;
		const before = get();
		if (next === DEFAULT) ROOT.removeAttribute(ATTR);
		else ROOT.setAttribute(ATTR, next);
		if (next !== before) notify(next);
		return next;
	}

	function notify(key) {
		try {
			document.dispatchEvent(new CustomEvent(EVENT, { detail: { density: key } }));
		} catch (_e) {
			/* CustomEvent unavailable — nothing listens on that browser either */
		}
	}

	function readCache() {
		try {
			const raw = localStorage.getItem(STORAGE_KEY);
			if (!raw) return null;
			const cached = JSON.parse(raw);
			if (!cached || typeof cached !== "object") return null;
			// A cache another user of this browser left is not ours to follow.
			const user = bootUser();
			if (user && cached.user !== user) return null;
			return normalize(cached.density);
		} catch (_e) {
			return null;
		}
	}

	function writeCache(key) {
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify({ user: bootUser(), density: key }));
		} catch (_e) {
			/* quota or disabled — non-fatal */
		}
	}

	/** The density boot carried, or null when boot has none. */
	function fromBoot() {
		const boot = window.frappe && frappe.boot;
		if (!boot) return null;
		if (boot.nexus_density && boot.nexus_density.density) {
			return normalize(boot.nexus_density.density);
		}
		// Also present inside the theme payload, for a boot from before
		// nexus_density stood on its own.
		if (boot.active_theme && boot.active_theme.density) {
			return normalize(boot.active_theme.density);
		}
		return null;
	}

	/**
	 * Persist and apply. The page changes at once so the choice feels
	 * immediate; if the server refuses, the previous density comes back and
	 * the error is rethrown for the caller to report. Resolves to the key
	 * the server settled on.
	 */
	async function set(key) {
		const next = normalize(key);
		if (!next) {
			throw new Error("Unknown density: " + key);
		}
		const previous = get();
		apply(next);
		if (!(window.frappe && frappe.call)) {
			writeCache(next);
			return next;
		}
		try {
			const r = await frappe.call({
				method: "nexus_theme.api.set_density",
				args: { density: next },
			});
			const settled = normalize(r && r.message && r.message.density) || next;
			apply(settled);
			writeCache(settled);
			return settled;
		} catch (e) {
			apply(previous);
			throw e;
		}
	}

	/**
	 * Agree with the server once the Desk is up. Boot is cached per user
	 * on the server and can be stale straight after a save in another
	 * session, in which case the server is asked directly, as
	 * theme_manager does for the theme.
	 */
	async function reconcile() {
		const f = window.frappe;
		if (!f) return;
		let key = null;
		if (f.boot && f.boot.from_cache && f.call) {
			try {
				const r = await f.call({ method: "nexus_theme.api.get_density" });
				key = normalize(r && r.message && r.message.density);
			} catch (_e) {
				/* fall back to what boot said */
			}
		}
		if (!key) key = fromBoot();
		if (!key) return;
		apply(key);
		writeCache(key);
	}

	// First paint: the boot value when there is one, else the cache.
	const initial = fromBoot() || readCache();
	if (initial) apply(initial);

	// Another tab of this browser changed it.
	window.addEventListener("storage", (e) => {
		if (e.key !== STORAGE_KEY) return;
		if (!e.newValue) {
			apply(DEFAULT);
			return;
		}
		const key = readCache();
		if (key) apply(key);
	});

	if (window.frappe && typeof frappe.ready === "function") {
		frappe.ready(reconcile);
	} else if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", reconcile);
	} else {
		reconcile();
	}

	// The public face. Theme Studio's control and the command palette call
	// these; `apply` is local only, `set` persists. Listen for
	// "nexus-density-change" on document to follow changes from anywhere.
	window.NexusDensity = { modes, get, set, apply };
})();
