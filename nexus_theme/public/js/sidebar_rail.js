(function () {
	"use strict";

	// ------------------------------------------------------------------
	// Mini rail: a collapsed, icon-only sidebar that remembers itself
	// ------------------------------------------------------------------
	// Frappe 16 already folds its app-wide `.body-sidebar` down to an icon
	// rail: `frappe.app.sidebar.toggle_width()` flips `sidebar_expanded`,
	// the container gains or loses `.expanded`, the state is kept in
	// localStorage under "sidebar-expanded", Ctrl+/ and the chevron on the
	// sidebar's edge both toggle it, and collapsed items get Bootstrap
	// tooltips from their own `title`. None of that is re-implemented
	// here. This file drives Frappe's own state and adds what it lacks:
	//
	//   * the choice is stored per person on the server (User Theme
	//     Preference.sidebar_collapsed), not per browser, and is applied
	//     from boot before the sidebar is first drawn;
	//   * Ctrl+Shift+B toggles it (Ctrl+B is Frappe 16's "new document"
	//     shortcut in list views, and bold in the text editor);
	//   * hovering the rail for a moment opens it as an overlay over the
	//     page, without reflowing the page, and leaving closes it again;
	//   * the expand chevron stays visible while collapsed, instead of
	//     only on hover (sidebar_rail.bundle.css), and the width change
	//     respects prefers-reduced-motion;
	//   * a window.NexusRail API, a "nexus-rail-change" event and two
	//     command palette entries.
	//
	// Frappe 15 has no app-wide sidebar. What it has is a side section per
	// page (`.layout-side-section`, list and workspace sidebars) and a
	// toggle button in each page head that shows or hides it. There the
	// same preference means "keep the side section hidden": it is applied
	// to each page as it is shown, through the same jQuery toggle Frappe's
	// button uses, and Frappe's button is listened to so a click there is
	// remembered too.
	//
	// Nothing happens on narrow screens. Frappe 16 turns its sidebar into
	// a drawer below 768px (frappe.is_mobile) and Frappe 15 turns the side
	// section into an overlay below 992px (is_xs / is_sm); both keep their
	// own behaviour there, and a toggle made there is not stored.
	// ------------------------------------------------------------------

	if (window.NexusRail) return;

	// Ours: {user, collapsed}, read before first paint and shared between
	// tabs. Scoped to the user because a browser can be shared.
	const STORAGE_KEY = "sidebar-rail:active";
	// Frappe 16's own key, read by Sidebar.load_sidebar_state() when the
	// sidebar is first drawn. Written here from boot so that first draw is
	// already right.
	const FRAPPE_KEY = "sidebar-expanded";
	const EVENT = "nexus-rail-change";
	const METHOD_SET = "nexus_theme.api.set_sidebar_collapsed";
	const METHOD_GET = "nexus_theme.api.get_sidebar_collapsed";
	// frappe.ui.keys spells shortcuts modifier-first, shift before ctrl
	// (keyboard.js get_key). ⌘ counts as ctrl there, so ⌘⇧B works on a Mac.
	const SHORTCUT = "shift+ctrl+b";

	// <html data-nexus-rail="collapsed|expanded" data-nexus-rail-host="v15|v16">
	// while the rail applies (wide enough); both are removed on a phone.
	const ATTR = "data-nexus-rail";
	const HOST_ATTR = "data-nexus-rail-host";
	const PEEK_ATTR = "data-nexus-rail-peek";
	const PEEK_CLASS = "nexus-rail-peek";
	// Marks a Frappe 15 side section whose inline display this file set.
	const V15_MARK = "data-nexus-rail-hidden";

	const V16_MIN_WIDTH = 768; // frappe.is_mobile(): innerWidth < 768
	const V15_MIN_WIDTH = 992; // frappe.utils.is_xs() / is_sm(): < 991
	const PEEK_DELAY_MS = 250;
	// A short grace on leaving, so brushing past the edge of the overlay
	// does not snap it shut.
	const UNPEEK_DELAY_MS = 120;
	const SAVE_DEBOUNCE_MS = 400;

	const ROOT = document.documentElement;

	const state = {
		collapsed: false,
		hooked: null, // the frappe.app.sidebar instance already patched
		saveTimer: null,
		peekTimer: null,
	};

	const T = (s) => (typeof window.__ === "function" ? window.__(s) : s);

	// ------------------------------------------------------------------
	// Where are we
	// ------------------------------------------------------------------

	/**
	 * True on Frappe 16, where the app-wide sidebar exists. Asked of the
	 * class rather than the instance so it answers before the Desk has
	 * started; Frappe 15 also has a frappe.ui.Sidebar, but a small one
	 * with no toggle_width.
	 */
	function hasAppSidebar() {
		const S = window.frappe && frappe.ui && frappe.ui.Sidebar;
		return !!(S && S.prototype && typeof S.prototype.toggle_width === "function");
	}

	/** The running Frappe 16 sidebar, or null before the Desk starts / on 15. */
	function appSidebar() {
		const sb = window.frappe && frappe.app && frappe.app.sidebar;
		return sb && typeof sb.toggle_width === "function" && sb.wrapper ? sb : null;
	}

	function wideEnough() {
		return window.innerWidth >= (hasAppSidebar() ? V16_MIN_WIDTH : V15_MIN_WIDTH);
	}

	/** The Frappe 15 page on screen, when it has a side section to hide. */
	function currentV15Page() {
		const el = window.frappe && frappe.container && frappe.container.page;
		const page = el && el.page;
		if (!page || page.disable_sidebar_toggle) return null;
		return page.sidebar && page.sidebar.length ? page : null;
	}

	/**
	 * Whether there is anything to toggle right now. Frappe 16 keeps a
	 * sidebar with no items open and hides its own chevron; collapsing
	 * that would leave an empty strip, so it is not offered.
	 */
	function available() {
		if (!wideEnough()) return false;
		if (hasAppSidebar()) {
			const sb = appSidebar();
			if (!sb) return false;
			const items = sb.workspace_sidebar_items;
			return !(Array.isArray(items) && items.length === 0);
		}
		return !!currentV15Page();
	}

	// ------------------------------------------------------------------
	// Cache and boot
	// ------------------------------------------------------------------

	function bootUser() {
		const f = window.frappe;
		if (!f) return null;
		if (f.boot && f.boot.user && f.boot.user.name) return f.boot.user.name;
		return (f.session && f.session.user) || null;
	}

	function asFlag(value) {
		if (value === true || value === 1 || value === "1") return true;
		if (value === false || value === 0 || value === "0") return false;
		return null;
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
			return asFlag(cached.collapsed);
		} catch (_e) {
			return null;
		}
	}

	function writeCache(collapsed) {
		try {
			localStorage.setItem(
				STORAGE_KEY,
				JSON.stringify({ user: bootUser(), collapsed: !!collapsed })
			);
		} catch (_e) {
			/* quota or disabled — non-fatal */
		}
	}

	/** Boot's answer (true / false), or null when boot has none. */
	function fromBoot() {
		const boot = window.frappe && frappe.boot;
		if (!boot) return null;
		const direct = asFlag(boot.nexus_sidebar_collapsed);
		if (direct !== null) return direct;
		// Also inside the theme payload, for a boot that has only that.
		return boot.active_theme ? asFlag(boot.active_theme.sidebar_collapsed) : null;
	}

	/** Hand the choice to Frappe 16's own storage, read on first draw. */
	function seedFrappe() {
		if (!hasAppSidebar() || !wideEnough()) return;
		try {
			localStorage.setItem(FRAPPE_KEY, JSON.stringify(!state.collapsed));
		} catch (_e) {
			/* non-fatal: Frappe then draws its last state and is corrected below */
		}
	}

	// ------------------------------------------------------------------
	// Applying the state
	// ------------------------------------------------------------------

	function markRoot() {
		if (wideEnough()) {
			ROOT.setAttribute(ATTR, state.collapsed ? "collapsed" : "expanded");
			ROOT.setAttribute(HOST_ATTR, hasAppSidebar() ? "v16" : "v15");
		} else {
			ROOT.removeAttribute(ATTR);
			ROOT.removeAttribute(HOST_ATTR);
			peek(false);
		}
	}

	/** Bring Frappe 16's sidebar into line, through its own open/close. */
	function driveV16() {
		seedFrappe();
		const sb = appSidebar();
		if (!sb || !wideEnough()) return;
		// open() and close() end in sidebar_header.toggle_width(), and the
		// header is only built with the first workspace. Until then there is
		// nothing to drive: seedFrappe() above has already written the choice
		// where Frappe reads it when it draws that header.
		if (!sb.sidebar_header) return;
		if (!!sb.sidebar_expanded === !state.collapsed) return;
		if (state.collapsed && !available()) return; // nothing to fold away
		peek(false);
		if (state.collapsed) sb.close();
		else sb.open();
	}

	/**
	 * Show or hide the current Frappe 15 page's side section. `.toggle()`
	 * is what Frappe's own page-head button calls; update_sidebar_icon()
	 * then flips that button's icon to match.
	 */
	function driveV15() {
		const page = currentV15Page();
		if (!page) return;
		const $side = page.sidebar;
		if (!wideEnough()) {
			// The overlay sidebar Frappe uses on a narrow screen lives inside
			// this section; an inline display:none left by us would bury it.
			if ($side.attr(V15_MARK)) {
				$side.css("display", "");
				$side.removeAttr(V15_MARK);
			}
			return;
		}
		$side.toggle(!state.collapsed);
		$side.attr(V15_MARK, "1");
		if (typeof page.update_sidebar_icon === "function") {
			try {
				page.update_sidebar_icon();
			} catch (_e) {
				/* icon only */
			}
		}
	}

	function drive() {
		if (hasAppSidebar()) driveV16();
		else driveV15();
	}

	function notify() {
		try {
			document.dispatchEvent(
				new CustomEvent(EVENT, { detail: { collapsed: state.collapsed } })
			);
		} catch (_e) {
			/* CustomEvent unavailable — nothing listens on that browser either */
		}
	}

	/** Set the state locally: attribute, Frappe's sidebar, event. */
	function applyLocal(collapsed) {
		const next = !!collapsed;
		const changed = next !== state.collapsed;
		state.collapsed = next;
		markRoot();
		drive();
		if (changed) notify();
		return next;
	}

	// ------------------------------------------------------------------
	// Saving
	// ------------------------------------------------------------------

	async function persist(collapsed) {
		const r = await frappe.call({
			method: METHOD_SET,
			args: { collapsed: collapsed ? 1 : 0 },
		});
		const settled = asFlag(r && r.message && r.message.collapsed);
		return settled === null ? !!collapsed : settled;
	}

	/**
	 * A toggle made through Frappe's own controls (chevron, Ctrl+/, the
	 * "Toggle Sidebar" menu item, Frappe 15's page-head button). The page
	 * has already changed; this only records it. Saves are coalesced so a
	 * burst of toggles is one request.
	 */
	function recordUserToggle(collapsed) {
		if (!wideEnough()) return;
		if (!!collapsed === state.collapsed) return;
		state.collapsed = !!collapsed;
		markRoot();
		seedFrappe();
		writeCache(state.collapsed);
		notify();
		if (!(window.frappe && frappe.call)) return;
		clearTimeout(state.saveTimer);
		state.saveTimer = setTimeout(() => {
			state.saveTimer = null;
			persist(state.collapsed).catch(() => {
				/* kept locally; the next change or reload tries again */
			});
		}, SAVE_DEBOUNCE_MS);
	}

	/**
	 * Collapse (true) or expand (false), and store it for this person.
	 * The page changes at once; if the server refuses, the previous state
	 * comes back and the error is rethrown. Resolves to the stored state.
	 */
	async function set(collapsed) {
		const next = !!collapsed;
		const previous = state.collapsed;
		clearTimeout(state.saveTimer);
		state.saveTimer = null;
		applyLocal(next);
		writeCache(next);
		if (!(window.frappe && frappe.call)) return next;
		try {
			const settled = await persist(next);
			applyLocal(settled);
			writeCache(settled);
			return settled;
		} catch (e) {
			applyLocal(previous);
			writeCache(previous);
			throw e;
		}
	}

	/**
	 * What the screen shows. On Frappe 16 that is Frappe's own flag, which
	 * can differ from the stored choice for a moment: clicking a section
	 * icon on the rail opens the sidebar without it being a new choice.
	 */
	function isCollapsed() {
		const sb = appSidebar();
		if (sb && wideEnough()) return !sb.sidebar_expanded;
		return state.collapsed;
	}

	function toggle() {
		return set(!isCollapsed());
	}

	// ------------------------------------------------------------------
	// Frappe 16: follow Frappe's own toggles, and peek on hover
	// ------------------------------------------------------------------

	function hookV16(sb) {
		if (!sb || state.hooked === sb) return;
		state.hooked = sb;

		// Every one of Frappe's controls ends in toggle_width(): the chevron,
		// the resize handle, Ctrl+/ and the settings menu's "Toggle Sidebar".
		// Frappe also opens the sidebar by itself (a workspace with no items,
		// a click on a section icon while collapsed) through open() or
		// expand_sidebar(), which are deliberately not followed: those are
		// not a choice to keep the sidebar open.
		const toggleWidth = sb.toggle_width;
		sb.toggle_width = function () {
			peek(false);
			const out = toggleWidth.apply(this, arguments);
			recordUserToggle(!this.sidebar_expanded);
			return out;
		};

		// Frappe re-reads its localStorage key each time it rebuilds the
		// sidebar for a workspace, and that key is rewritten whenever it
		// opens by itself — so one visit to a workspace with no items used
		// to leave every later one open. The stored choice answers instead;
		// Frappe still forces an item-less sidebar open right after this.
		const loadState = sb.load_sidebar_state;
		if (typeof loadState === "function") {
			sb.load_sidebar_state = function () {
				const out = loadState.apply(this, arguments);
				if (wideEnough()) this.sidebar_expanded = !state.collapsed;
				return out;
			};
		}

		$(document).on("sidebar-expand", (_e, info) => {
			if (info && info.sidebar_expand) peek(false);
		});

		setupPeek(sb);
		driveV16();
	}

	function railShowing() {
		const sb = appSidebar();
		return !!(sb && wideEnough() && !sb.sidebar_expanded);
	}

	function peek(on) {
		clearTimeout(state.peekTimer);
		state.peekTimer = null;
		const sb = appSidebar();
		const show = !!on && railShowing();
		if (sb) sb.wrapper.toggleClass(PEEK_CLASS, show);
		if (show) ROOT.setAttribute(PEEK_ATTR, "");
		else ROOT.removeAttribute(PEEK_ATTR);
	}

	function peekLater(on, delay) {
		clearTimeout(state.peekTimer);
		state.peekTimer = setTimeout(() => peek(on), delay);
	}

	function setupPeek(sb) {
		const bar = sb.wrapper.find(".body-sidebar")[0];
		if (!bar) return;
		// A touch screen fires mouseenter on tap; the tap is meant for the
		// icon under the finger, not for opening the sidebar.
		const canHover = !window.matchMedia || window.matchMedia("(hover: hover)").matches;

		if (canHover) {
			bar.addEventListener("mouseenter", () => {
				if (railShowing()) peekLater(true, PEEK_DELAY_MS);
			});
			bar.addEventListener("mouseleave", () => {
				if (ROOT.hasAttribute(PEEK_ATTR)) peekLater(false, UNPEEK_DELAY_MS);
				else peek(false);
			});
		}

		// Tabbing into the rail opens it too, so a keyboard user can read
		// the labels. Only for keyboard focus: a mouse click also focuses
		// the link, and the overlay must not stay open after the pointer
		// has gone.
		bar.addEventListener("focusin", (e) => {
			let keyboard = false;
			try {
				keyboard = e.target.matches(":focus-visible");
			} catch (_e) {
				keyboard = false;
			}
			if (keyboard && railShowing()) peek(true);
		});
		bar.addEventListener("focusout", (e) => {
			if (!bar.contains(e.relatedTarget) && !bar.matches(":hover")) peek(false);
		});
		document.addEventListener("keydown", (e) => {
			if (e.key === "Escape" && ROOT.hasAttribute(PEEK_ATTR)) peek(false);
		});
	}

	// ------------------------------------------------------------------
	// Frappe 15: apply per page, follow the page-head button
	// ------------------------------------------------------------------

	function hookV15() {
		// A page's side section exists once the page is made, which is
		// before page-change; its contents may come later, which does not
		// matter for showing or hiding it.
		$(document).on("page-change", () => {
			markRoot();
			requestAnimationFrame(driveV15);
			// A page seen for the first time may be made just after the
			// change; sidebar_rail.bundle.css keeps its section hidden
			// meanwhile, and this second pass sets the button's icon.
			setTimeout(driveV15, 300);
		});
		// Frappe's page-head button toggles the section, then triggers this.
		$(document.body).on("toggleSidebar", () => {
			const page = currentV15Page();
			if (!page || !wideEnough()) return;
			page.sidebar.attr(V15_MARK, "1");
			recordUserToggle(!page.sidebar.is(":visible"));
		});
		driveV15();
	}

	// ------------------------------------------------------------------
	// Shortcut and command palette
	// ------------------------------------------------------------------

	function shortcutLabel() {
		const keys = window.frappe && frappe.ui && frappe.ui.keys;
		if (keys && typeof keys.get_shortcut_label === "function") {
			try {
				return keys.get_shortcut_label(SHORTCUT);
			} catch (_e) {
				/* fall through */
			}
		}
		return "Ctrl+Shift+B";
	}

	function report(err) {
		if (window.frappe && typeof frappe.show_alert === "function") {
			frappe.show_alert({
				message: T("Could not save the sidebar setting."),
				indicator: "red",
			});
		}
		if (window.console) console.error("NexusRail:", err);
	}

	function bindShortcut() {
		const keys = window.frappe && frappe.ui && frappe.ui.keys;
		if (!keys || typeof keys.add_shortcut !== "function") return;
		keys.add_shortcut({
			shortcut: SHORTCUT,
			action: () => {
				// Returning false leaves the key to the browser when there is
				// no sidebar to fold (a phone-width window, a page without one).
				if (!available()) return false;
				toggle().catch(report);
			},
			description: T("Collapse or expand the sidebar"),
		});
	}

	function registerCommands() {
		const palette = window.NexusCommandPalette;
		if (!palette || typeof palette.register !== "function") return;
		const hint = shortcutLabel();
		const keywords = ["sidebar", "rail", "mini", "icons", "panel", "navigation"];
		palette.register({
			id: "nexus-rail-collapse",
			group: "actions",
			label: T("Collapse sidebar"),
			hint,
			keywords: keywords.concat(["hide", "fold", "narrow"]),
			when: () => available() && !isCollapsed(),
			run: () => set(true).catch(report),
		});
		palette.register({
			id: "nexus-rail-expand",
			group: "actions",
			label: T("Expand sidebar"),
			hint,
			keywords: keywords.concat(["show", "unfold", "wide"]),
			when: () => available() && isCollapsed(),
			run: () => set(false).catch(report),
		});
	}

	// ------------------------------------------------------------------
	// Start
	// ------------------------------------------------------------------

	/**
	 * Agree with the server once the Desk is up. Boot is cached per user
	 * on the server and can be stale right after a change in another
	 * session; then the server is asked directly, as density.js does.
	 */
	async function reconcile() {
		const f = window.frappe;
		if (!(f && f.boot && f.boot.from_cache && f.call)) return;
		try {
			const r = await f.call({ method: METHOD_GET });
			const collapsed = asFlag(r && r.message && r.message.collapsed);
			if (collapsed === null) return;
			applyLocal(collapsed);
			writeCache(collapsed);
		} catch (_e) {
			/* keep what boot said */
		}
	}

	/**
	 * Call `fn` with the running Frappe 16 sidebar as soon as there is one.
	 *
	 * Frappe fires app_ready from inside the Application constructor, before
	 * `frappe.app` has been assigned, so at that moment frappe.app.sidebar
	 * does not exist yet even though the sidebar has been built. Hooking
	 * straight away silently hooked nothing: no hover-to-peek, and Frappe's
	 * own chevron and Ctrl+/ were never saved. The assignment lands as soon
	 * as the constructor returns, so a few turns of the event loop is
	 * always enough; the cap only guards against a Desk that never starts.
	 */
	function whenAppSidebar(fn, tries = 0) {
		const sb = appSidebar();
		if (sb) {
			fn(sb);
			return;
		}
		if (tries < 100) setTimeout(() => whenAppSidebar(fn, tries + 1), 20);
	}

	let started = false;
	function start() {
		if (started) return;
		started = true;
		if (hasAppSidebar()) whenAppSidebar(hookV16);
		else hookV15();
		bindShortcut();
		registerCommands();
		reconcile();
	}

	/** Frappe 16's own last state in this browser, or null. */
	function frappeLocal() {
		try {
			const raw = localStorage.getItem(FRAPPE_KEY);
			return raw === null ? null : asFlag(JSON.parse(raw) === false);
		} catch (_e) {
			return null;
		}
	}

	// First paint. frappe.boot is set inline in desk.html ahead of every app
	// bundle and the Desk only starts on DOM ready, so on Frappe 16 this
	// runs before the sidebar is drawn and Frappe draws it the right way
	// the first time. Boot wins; the cache covers a boot without the key,
	// and with neither, whatever Frappe last drew in this browser stands.
	function firstPaint() {
		const boot = fromBoot();
		let initial = boot;
		if (initial === null) initial = readCache();
		if (initial === null && hasAppSidebar()) initial = frappeLocal();
		state.collapsed = initial === true;
		markRoot();
		seedFrappe();
		if (boot !== null) writeCache(boot);
	}

	firstPaint();

	// Another tab of this browser changed it; that tab has saved it.
	window.addEventListener("storage", (e) => {
		if (e.key !== STORAGE_KEY) return;
		const collapsed = readCache();
		if (collapsed !== null) applyLocal(collapsed);
	});

	// Rotating a tablet or resizing across a breakpoint: re-apply, so the
	// rail comes back when there is room again and stays out of the way of
	// the phone drawer when there is not.
	let resizeTimer = null;
	window.addEventListener("resize", () => {
		clearTimeout(resizeTimer);
		resizeTimer = setTimeout(() => {
			markRoot();
			drive();
		}, 150);
	});

	// app_include_js runs before the Desk starts on DOM ready, so this
	// normally waits for app_ready; the first branch covers a late load.
	if (window.frappe && frappe.Application && frappe.app instanceof frappe.Application) {
		start();
	} else if (window.jQuery) {
		$(document).one("app_ready", start);
	}

	// The public face. `set` persists; listen for "nexus-rail-change" on
	// document to follow changes from anywhere (detail: {collapsed}).
	window.NexusRail = { isCollapsed, set, toggle };
})();
