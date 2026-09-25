(function () {
	"use strict";

	// ------------------------------------------------------------------
	// Command palette
	// ------------------------------------------------------------------
	// Ctrl+K (⌘K on a Mac), or Ctrl+Shift+P, opens one panel that reaches
	// everything the keyboard could otherwise not: documents opened
	// recently, the app's own actions (the studios, switching themes,
	// density, sounds), every DocType, Report, Page and Workspace the user
	// may see, and — once the query is two characters long — a document
	// search through Frappe's global search index.
	//
	// It is plain DOM rather than frappe.ui.Dialog on purpose. A Dialog
	// waits for a Bootstrap modal transition and fights any modal that is
	// already open, while this has to be on screen in the frame the key is
	// pressed, on top of whatever is there.
	//
	// Frappe 16 binds Ctrl+K to the awesomebar (Frappe 15 leaves the key
	// free). frappe.ui.keys.add_shortcut() drops every handler a key
	// already has before it attaches its own, so registering ours is what
	// replaces that binding. Ctrl+G, Frappe's global search, is not touched.
	//
	// Everything shown here — DocType names, document names, titles from
	// the search index — is put on the page with textContent, never as
	// HTML. The only markup built by hand is the <mark> around matched
	// characters, and it wraps text nodes.
	// ------------------------------------------------------------------

	// Registering twice (the bundle evaluated a second time, or a page
	// that includes it on its own) must not bind the shortcut twice.
	if (window.NexusCommandPalette) return;

	const GROUPS = [
		{ key: "recent", label: "Recent", cap: 5 },
		{ key: "actions", label: "Actions", cap: 12 },
		{ key: "goto", label: "Go to", cap: 40 },
		{ key: "search", label: "Search", cap: 10 },
	];
	const TOTAL_CAP = 40;
	const SEARCH_MIN_CHARS = 2;
	const SEARCH_DEBOUNCE_MS = 200;
	const THEME_LIST_TTL_MS = 60 * 1000;

	/** Translate through Frappe when it is there; the palette also runs on a bare page. */
	function T(text, args) {
		if (typeof window.__ === "function") return window.__(text, args);
		if (!args) return text;
		return text.replace(/\{(\d+)\}/g, (m, i) => (args[i] == null ? m : String(args[i])));
	}

	function hasRole(role) {
		const f = window.frappe;
		const roles =
			(f && f.user_roles) || (f && f.boot && f.boot.user && f.boot.user.roles) || [];
		return roles.indexOf(role) !== -1;
	}

	function isMac() {
		const f = window.frappe;
		if (f && f.utils && typeof f.utils.is_mac === "function") return f.utils.is_mac();
		return /Mac|iPhone|iPad|iPod/.test(navigator.platform || "");
	}

	function setRoute() {
		if (window.frappe && typeof frappe.set_route === "function") {
			return frappe.set_route.apply(frappe, arguments);
		}
	}

	// ------------------------------------------------------------------
	// Fuzzy matching
	// ------------------------------------------------------------------
	// Case-insensitive subsequence match with a small score. A whole
	// substring wins outright; otherwise each query character is matched
	// left to right, preferring the next word start over a stray letter in
	// the middle of a word (so "od" on "Order Delivery" lands on the D of
	// Delivery, not the d of Order), with bonuses for a prefix, a word
	// start and an unbroken run. Pure: no DOM, no Frappe.
	// ------------------------------------------------------------------

	const WORD_CHAR = /[\p{L}\p{N}]/u;

	function isWordStart(text, i) {
		return i === 0 || !WORD_CHAR.test(text[i - 1]);
	}

	function isSubsequence(query, text, from) {
		let i = from;
		for (const c of query) {
			i = text.indexOf(c, i);
			if (i === -1) return false;
			i++;
		}
		return true;
	}

	/**
	 * Match `query` against `text`.
	 * Returns `{ score, positions }` — the indexes of `text` that matched —
	 * or null when there is no match. An empty query matches everything
	 * with a score of 0.
	 */
	function fuzzyMatch(query, text) {
		const q = String(query || "").toLowerCase();
		const t = String(text || "").toLowerCase();
		if (!q) return { score: 0, positions: [] };
		if (q.length > t.length) return null;

		const at = t.indexOf(q);
		if (at !== -1) {
			const positions = [];
			for (let i = 0; i < q.length; i++) positions.push(at + i);
			let score = 100 + q.length * 4;
			if (at === 0) score += 40;
			else if (isWordStart(t, at)) score += 20;
			score -= Math.min(at, 20) * 0.5;
			score -= (t.length - q.length) * 0.05;
			return { score, positions };
		}

		const positions = [];
		let score = 0;
		let from = 0;
		let prev = -2;
		for (let qi = 0; qi < q.length; qi++) {
			const c = q[qi];
			let pos = t.indexOf(c, from);
			if (pos === -1) return null;
			// Not continuing a run and not at a word start: look for the same
			// character at a word start further on, as long as the rest of
			// the query still fits after it.
			if (pos !== prev + 1 && !isWordStart(t, pos)) {
				const rest = q.slice(qi + 1);
				for (let k = pos + 1; k < t.length; k++) {
					if (t[k] === c && isWordStart(t, k) && isSubsequence(rest, t, k + 1)) {
						pos = k;
						break;
					}
				}
			}
			score += 4;
			if (isWordStart(t, pos)) score += 8;
			if (pos === prev + 1) score += 6;
			score -= Math.min(pos - from, 10) * 0.5;
			positions.push(pos);
			prev = pos;
			from = pos + 1;
		}
		if (positions[0] === 0) score += 15;
		score -= (t.length - q.length) * 0.05;
		return { score, positions };
	}

	/**
	 * Match every word of the query, in any order, against a command's
	 * label and keywords. Returns null unless every word matches somewhere.
	 * Positions refer to the label only; a match on a keyword counts for
	 * less and highlights nothing.
	 */
	function matchCommand(words, cmd) {
		let total = 0;
		const positions = new Set();
		for (const word of words) {
			let best = null;
			const onLabel = fuzzyMatch(word, cmd.label);
			if (onLabel) {
				best = onLabel.score;
				onLabel.positions.forEach((p) => positions.add(p));
			}
			for (const kw of cmd.keywords || []) {
				const m = fuzzyMatch(word, kw);
				if (m && (best === null || m.score * 0.8 > best)) best = m.score * 0.8;
			}
			if (best === null) return null;
			total += best;
		}
		return { score: total, positions: Array.from(positions).sort((a, b) => a - b) };
	}

	// ------------------------------------------------------------------
	// Command sources
	// ------------------------------------------------------------------
	// Each returns plain objects: { group, label, hint, keywords, run }.
	// They are rebuilt on every open, so the lists follow the Desk (a
	// theme saved a moment ago, a form just visited) without bookkeeping.
	// ------------------------------------------------------------------

	function recentCommands() {
		const f = window.frappe;
		if (!f) return [];
		const out = [];
		const seen = new Set();
		let current = null;
		try {
			const r = typeof f.get_route === "function" ? f.get_route() : null;
			if (r && r[0] === "Form" && r.length > 2) current = r[1] + "\u0000" + r[2];
		} catch (_e) {
			/* no router yet */
		}
		const push = (doctype, name) => {
			if (!doctype || name == null || name === "") return;
			name = String(name);
			const key = doctype + "\u0000" + name;
			if (seen.has(key) || key === current) return;
			seen.add(key);
			out.push({
				group: "recent",
				label: name,
				hint: T(doctype),
				keywords: [doctype],
				run: () => setRoute("Form", doctype, name),
			});
		};
		// This session first, newest last in route_history …
		const history = Array.isArray(f.route_history) ? f.route_history : [];
		for (let i = history.length - 1; i >= 0; i--) {
			const r = history[i];
			if (Array.isArray(r) && r[0] === "Form" && r.length > 2 && r[1] !== r[2]) {
				push(r[1], r[2]);
			}
		}
		// … then what the server remembers across sessions: a JSON list of
		// [doctype, name] pairs, oldest first (frappe.sessions puts it on
		// boot.user.recent on both 15 and 16; it is "null" for a new user).
		let remembered = [];
		try {
			const raw = f.boot && f.boot.user && f.boot.user.recent;
			remembered = typeof raw === "string" ? JSON.parse(raw) : raw;
		} catch (_e) {
			remembered = [];
		}
		if (Array.isArray(remembered)) {
			for (let i = remembered.length - 1; i >= 0; i--) {
				const r = remembered[i];
				if (Array.isArray(r)) push(r[0], r[1]);
			}
		}
		return out.slice(0, 25);
	}

	function toggleFrappeTheme() {
		const root = document.documentElement;
		const now = (
			root.getAttribute("data-theme-mode") ||
			root.getAttribute("data-theme") ||
			"light"
		).toLowerCase();
		const next = now === "dark" ? "light" : "dark";
		// The order matters: theme_manager.js watches data-theme-mode and
		// hands the Desk to Frappe on that write, exactly as it does for
		// Frappe's own Switch Theme dialog.
		root.setAttribute("data-theme-mode", next);
		if (window.frappe && frappe.ui && typeof frappe.ui.set_theme === "function") {
			frappe.ui.set_theme(next);
		} else {
			root.setAttribute("data-theme", next);
		}
		if (window.frappe && typeof frappe.xcall === "function") {
			frappe
				.xcall("frappe.core.doctype.user.user.switch_theme", {
					theme: next === "dark" ? "Dark" : "Light",
				})
				.catch(() => {});
		}
	}

	function logOut() {
		const f = window.frappe;
		if (f && f.app && typeof f.app.logout === "function") return f.app.logout();
		if (f && typeof f.call === "function") {
			return f.call({ method: "logout" }).then(() => {
				window.location.href = "/login";
			});
		}
		window.location.href = "/?cmd=web_logout";
	}

	function actionCommands(themes) {
		const out = [];
		const add = (label, run, extra) =>
			out.push(Object.assign({ group: "actions", label, run }, extra || {}));
		const manager = hasRole("System Manager");

		if (typeof window.openThemeSwitcher === "function") {
			add(T("Open Theme Studio"), () => window.openThemeSwitcher(), {
				keywords: ["theme", "colour", "color", "palette"],
			});
		}
		if (typeof window.openSoundStudio === "function") {
			add(T("Open Sound Studio"), () => window.openSoundStudio(), {
				keywords: ["sound", "audio"],
			});
		}
		if (manager) {
			add(T("Open Permission Inspector"), () => setRoute("nexus-permission-inspector"), {
				keywords: ["permission", "role"],
			});
			add(
				T("Open Theme Settings"),
				() => setRoute("Form", "Theme Settings", "Theme Settings"),
				{
					keywords: ["theme", "settings", "site"],
				}
			);
		}

		const tm = window.ThemeManager;
		if (tm && typeof tm.setActive === "function") {
			const activeName = tm.active && tm.active.name;
			(themes || []).forEach((theme) => {
				if (!theme || !theme.name) return;
				const dark = theme.is_dark && theme.is_dark !== "0";
				const current = theme.name === activeName;
				add(
					T("Switch theme → {0}", [theme.theme_name || theme.name]),
					() => tm.setActive(theme.name, {}),
					{
						keywords: ["theme", "switch", dark ? "dark" : "light"],
						hint: current ? T("Current") : dark ? T("Dark") : T("Light"),
					}
				);
			});
			if (tm.active && typeof tm.resetToFrappeDefault === "function") {
				add(T("Use Frappe's own theme"), () => tm.resetToFrappeDefault(), {
					keywords: ["theme", "reset", "default", "frappe"],
				});
			}
		}
		// Flipping light/dark is only well defined on Frappe's own look:
		// with one of the app's themes showing there is no "other half" to
		// flip to, and in Automatic mode the system decides.
		if (!(tm && tm.active)) {
			const mode = (
				document.documentElement.getAttribute("data-theme-mode") || "light"
			).toLowerCase();
			if (mode !== "automatic") {
				add(T("Toggle light/dark"), toggleFrappeTheme, {
					keywords: ["theme", "dark", "light", "mode"],
					hint: mode === "dark" ? T("Now dark") : T("Now light"),
				});
			}
		}

		// Density modes ship in their own bundle; the palette must not
		// depend on it being there.
		const density = window.NexusDensity;
		if (density && typeof density.modes === "function" && typeof density.set === "function") {
			let modes = [];
			let current = null;
			try {
				modes = density.modes() || [];
				current = typeof density.get === "function" ? density.get() : null;
			} catch (_e) {
				modes = [];
			}
			modes.forEach((m) => {
				if (!m || !m.key) return;
				add(T("Density → {0}", [m.label || m.key]), () => density.set(m.key), {
					keywords: ["density", "compact", "spacing", m.key],
					hint: m.key === current ? T("Current") : "",
				});
			});
		}

		const sm = window.SoundManager;
		if (sm && typeof sm.setEnabled === "function" && sm.customAllowed !== false) {
			const enabled = sm.enabled !== false;
			add(
				enabled ? T("Mute sounds") : T("Unmute sounds"),
				() => toggleSounds(sm, !enabled),
				{
					keywords: ["sound", "mute", "silence", "audio"],
				}
			);
		}

		add(T("Reload"), () => window.location.reload(), { keywords: ["refresh", "page"] });
		add(T("Log out"), logOut, { keywords: ["logout", "sign out", "exit"] });
		return out;
	}

	function toggleSounds(sm, enable) {
		if (!(window.frappe && typeof frappe.call === "function")) {
			sm.setEnabled(enable);
			return;
		}
		return frappe
			.call({
				method: "nexus_theme.api.toggle_user_sounds",
				args: { enabled: enable ? 1 : 0 },
			})
			.then(() => {
				sm.setEnabled(enable);
				if (typeof frappe.show_alert === "function") {
					frappe.show_alert({
						message: enable ? T("Sounds on") : T("Sounds muted"),
						indicator: "green",
					});
				}
			});
	}

	function workspaceCommands(boot) {
		const out = [];
		// v15 puts the list on boot.allowed_workspaces; v16 on
		// boot.workspaces.pages (desk.js copies it to allowed_workspaces at
		// startup). v16 also lists sidebar links and URLs as workspaces of
		// another `type`; those are not pages to go to.
		const pages = boot.allowed_workspaces || (boot.workspaces && boot.workspaces.pages) || [];
		const slug = (name) =>
			window.frappe && frappe.router && typeof frappe.router.slug === "function"
				? frappe.router.slug(name)
				: String(name).toLowerCase().replace(/ /g, "-");
		pages.forEach((p) => {
			if (!p || !p.name) return;
			if (p.type && p.type !== "Workspace") return;
			out.push({
				group: "goto",
				label: T(p.title || p.name),
				hint: T("Workspace"),
				keywords: [p.name, "workspace"],
				run: () => setRoute(slug(p.name)),
			});
		});
		return out;
	}

	function pageCommands(boot) {
		const out = [];
		const info = boot.page_info || {};
		Object.keys(info).forEach((name) => {
			const p = info[name] || {};
			out.push({
				group: "goto",
				label: T(p.title || name),
				hint: T("Page"),
				keywords: [name, "page"],
				run: () => setRoute(p.route || name),
			});
		});
		return out;
	}

	function reportCommands(boot) {
		const out = [];
		const reports = (boot.user && boot.user.all_reports) || {};
		Object.keys(reports).forEach((name) => {
			const r = reports[name] || {};
			const route =
				r.report_type === "Report Builder"
					? ["List", r.ref_doctype, "Report", name]
					: ["query-report", name];
			out.push({
				group: "goto",
				label: T(name),
				hint: T("Report"),
				keywords: [r.ref_doctype || "", "report"],
				run: () => setRoute(route),
			});
		});
		return out;
	}

	function doctypeCommands(boot) {
		const out = [];
		const user = boot.user || {};
		const canRead = user.can_read || [];
		const canCreate = new Set(user.can_create || []);
		// can_search is the set with a list view (no child tables, no
		// read-only doctypes). Without it, everything readable is offered.
		const canSearch = Array.isArray(user.can_search) ? new Set(user.can_search) : null;
		const singles = new Set(boot.single_types || []);
		const trees = new Set(boot.tree_view_doctypes || []);
		canRead.forEach((dt) => {
			if (singles.has(dt)) {
				out.push({
					group: "goto",
					label: T(dt),
					hint: T("Settings"),
					keywords: [dt],
					run: () => setRoute("Form", dt, dt),
				});
				return;
			}
			if (canSearch && !canSearch.has(dt)) return;
			const tree = trees.has(dt);
			out.push({
				group: "goto",
				label: T(dt),
				hint: tree ? T("Tree") : T("List"),
				keywords: [dt],
				run: () => setRoute(tree ? "Tree" : "List", dt),
			});
			if (canCreate.has(dt)) {
				out.push({
					group: "goto",
					label: T("New {0}", [T(dt)]),
					hint: T("New"),
					keywords: [dt, "new", "create"],
					run: () => {
						if (window.frappe && typeof frappe.new_doc === "function")
							frappe.new_doc(dt);
					},
				});
			}
		});
		return out;
	}

	function gotoCommands() {
		const boot = (window.frappe && frappe.boot) || {};
		// Order matters for an empty query, where the group is shown as-is:
		// a handful of workspaces and pages is worth more than the first
		// forty DocTypes of the alphabet.
		return []
			.concat(workspaceCommands(boot))
			.concat(pageCommands(boot))
			.concat(reportCommands(boot))
			.concat(doctypeCommands(boot));
	}

	// ------------------------------------------------------------------
	// Theme list (async, cached briefly)
	// ------------------------------------------------------------------

	let themeCache = { at: 0, themes: null, pending: null };

	function loadThemes(onReady) {
		if (!(window.frappe && typeof frappe.call === "function")) return;
		if (themeCache.themes && Date.now() - themeCache.at < THEME_LIST_TTL_MS) return;
		if (themeCache.pending) {
			// A fetch from a previous open is still on its way; ride on it.
			themeCache.pending.then(onReady, () => {});
			return;
		}
		themeCache.pending = frappe
			.call({ method: "nexus_theme.api.get_available_themes" })
			.then((r) => {
				const m = (r && r.message) || {};
				const all = []
					.concat(m.defaults || [])
					.concat(m.owned || [])
					.concat(m.public || []);
				themeCache = { at: Date.now(), themes: all, pending: null };
				onReady();
			})
			.catch(() => {
				themeCache.pending = null;
			});
	}

	// ------------------------------------------------------------------
	// State and DOM
	// ------------------------------------------------------------------

	const state = {
		open: false,
		query: "",
		commands: [],
		visible: [], // [{cmd, positions}] in display order, headings excluded
		selected: 0,
		searchFor: null, // the query the search results belong to
		searchResults: [],
		searching: false,
		restoreFocus: null,
	};
	const extras = new Map(); // commands added through register()
	let extraSeq = 0;
	let searchSeq = 0;
	let searchTimer = null;

	let dom = null;

	function el(tag, className, text) {
		const node = document.createElement(tag);
		if (className) node.className = className;
		if (text != null) node.textContent = text;
		return node;
	}

	function kbd(text) {
		return el("kbd", "nxt-cp-kbd", text);
	}

	function build() {
		if (dom) return dom;
		const overlay = el("div", "nxt-cp-overlay");
		overlay.hidden = true;

		const panel = el("div", "nxt-cp");
		panel.setAttribute("role", "dialog");
		panel.setAttribute("aria-modal", "true");
		panel.setAttribute("aria-label", T("Command palette"));

		const head = el("div", "nxt-cp-head");
		const icon = el("span", "nxt-cp-search-icon");
		icon.setAttribute("aria-hidden", "true");
		icon.innerHTML =
			'<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg>';
		const input = el("input", "nxt-cp-input");
		input.type = "text";
		input.placeholder = T("Type a command, a DocType or a document name…");
		input.autocomplete = "off";
		input.spellcheck = false;
		input.setAttribute("role", "combobox");
		input.setAttribute("aria-autocomplete", "list");
		input.setAttribute("aria-expanded", "true");
		input.setAttribute("aria-controls", "nxt-cp-list");
		const shortcut = kbd(isMac() ? "⌘K" : "Ctrl+K");
		shortcut.classList.add("nxt-cp-shortcut");
		head.append(icon, input, shortcut);

		const body = el("div", "nxt-cp-body");
		const list = el("ul", "nxt-cp-list");
		list.id = "nxt-cp-list";
		list.setAttribute("role", "listbox");
		const empty = el("div", "nxt-cp-empty");
		empty.hidden = true;
		empty.append(el("div", "nxt-cp-empty-title"), el("div", "nxt-cp-empty-hint"));
		body.append(list, empty);

		const foot = el("div", "nxt-cp-foot");
		const nav = el("span", "nxt-cp-foot-item");
		nav.append(kbd("↑"), kbd("↓"), document.createTextNode(" " + T("navigate")));
		const open = el("span", "nxt-cp-foot-item");
		open.append(kbd("↵"), document.createTextNode(" " + T("open")));
		const esc = el("span", "nxt-cp-foot-item");
		esc.append(kbd("esc"), document.createTextNode(" " + T("close")));
		foot.append(nav, open, esc);

		panel.append(head, body, foot);
		overlay.append(panel);
		document.body.append(overlay);

		// Clicking the dim outside the panel closes; anything inside keeps
		// the focus where it is (mousedown on the list would otherwise pull
		// it off the input).
		overlay.addEventListener("mousedown", (e) => {
			if (e.target === overlay) {
				e.preventDefault();
				close();
			}
		});
		panel.addEventListener("mousedown", (e) => {
			if (e.target !== input) e.preventDefault();
		});
		input.addEventListener("input", onInput);
		input.addEventListener("keydown", onKeyDown);
		list.addEventListener("click", (e) => {
			const item = e.target.closest ? e.target.closest(".nxt-cp-item") : null;
			if (!item) return;
			runAt(Number(item.dataset.index));
		});
		list.addEventListener("mousemove", (e) => {
			const item = e.target.closest ? e.target.closest(".nxt-cp-item") : null;
			if (!item) return;
			const i = Number(item.dataset.index);
			if (i !== state.selected) select(i, false);
		});

		dom = { overlay, panel, input, list, empty };
		return dom;
	}

	// ------------------------------------------------------------------
	// Filtering and rendering
	// ------------------------------------------------------------------

	function collectCommands() {
		const list = []
			.concat(recentCommands())
			.concat(actionCommands(themeCache.themes))
			.concat(Array.from(extras.values()))
			.concat(gotoCommands());
		return list.filter((c) => {
			if (!c || !c.label || typeof c.run !== "function") return false;
			if (typeof c.when === "function") {
				try {
					return !!c.when();
				} catch (_e) {
					return false;
				}
			}
			return true;
		});
	}

	function filter() {
		const query = state.query.trim();
		const words = query ? query.split(/\s+/) : [];
		const byGroup = {};
		GROUPS.forEach((g) => (byGroup[g.key] = []));

		if (words.length) {
			state.commands.forEach((cmd) => {
				const m = matchCommand(words, cmd);
				if (!m) return;
				(byGroup[cmd.group] || byGroup.actions).push({
					cmd,
					positions: m.positions,
					score: m.score,
				});
			});
			Object.keys(byGroup).forEach((k) => {
				byGroup[k].sort(
					(a, b) => b.score - a.score || a.cmd.label.localeCompare(b.cmd.label)
				);
			});
		} else {
			state.commands.forEach((cmd) => {
				(byGroup[cmd.group] || byGroup.actions).push({ cmd, positions: [], score: 0 });
			});
		}
		if (state.searchFor === query && query.length >= SEARCH_MIN_CHARS) {
			byGroup.search = state.searchResults.map((cmd) => ({ cmd, positions: [], score: 0 }));
		}

		// Recent and search rows have their own caps; actions a smaller
		// one; "Go to" takes whatever is left of the total.
		let budget = TOTAL_CAP;
		const sections = [];
		GROUPS.forEach((g) => {
			const rows = byGroup[g.key];
			if (!rows.length) return;
			const take = rows.slice(0, Math.min(g.cap, budget));
			if (!take.length) return;
			budget -= take.length;
			sections.push({ group: g, rows: take });
		});
		return sections;
	}

	function highlighted(label, positions) {
		const frag = document.createDocumentFragment();
		if (!positions.length) {
			frag.append(document.createTextNode(label));
			return frag;
		}
		const set = new Set(positions);
		let run = "";
		let marking = false;
		const flush = () => {
			if (!run) return;
			frag.append(marking ? el("mark", null, run) : document.createTextNode(run));
			run = "";
		};
		for (let i = 0; i < label.length; i++) {
			const m = set.has(i);
			if (m !== marking) {
				flush();
				marking = m;
			}
			run += label[i];
		}
		flush();
		return frag;
	}

	function render() {
		const d = build();
		const sections = filter();
		state.visible = [];
		d.list.textContent = "";

		sections.forEach(({ group, rows }) => {
			const heading = el("li", "nxt-cp-group", T(group.label));
			heading.setAttribute("role", "presentation");
			if (group.key === "search" && state.searching) {
				heading.append(el("span", "nxt-cp-group-note", T("searching…")));
			}
			d.list.append(heading);
			rows.forEach(({ cmd, positions }) => {
				const index = state.visible.length;
				state.visible.push({ cmd, positions });
				const item = el("li", "nxt-cp-item");
				item.id = "nxt-cp-item-" + index;
				item.dataset.index = String(index);
				item.setAttribute("role", "option");
				const label = el("span", "nxt-cp-label");
				label.append(highlighted(cmd.label, positions));
				item.append(label);
				if (cmd.hint) item.append(el("span", "nxt-cp-hint", cmd.hint));
				d.list.append(item);
			});
		});

		const query = state.query.trim();
		const pendingSearch = query.length >= SEARCH_MIN_CHARS && (state.searching || searchTimer);
		if (!state.visible.length) {
			const title = d.empty.firstChild;
			const hint = d.empty.lastChild;
			if (pendingSearch) {
				title.textContent = T("Searching…");
				hint.textContent = "";
			} else {
				title.textContent = query
					? T("No matches for “{0}”", [query])
					: T("Nothing to show");
				hint.textContent =
					query.length >= SEARCH_MIN_CHARS
						? T(
								"Try a DocType, a report or a workspace name. Documents are searched by their indexed fields."
						  )
						: T("Type at least two characters to search documents.");
			}
			d.empty.hidden = false;
		} else {
			d.empty.hidden = true;
		}
		select(Math.min(state.selected, Math.max(0, state.visible.length - 1)), false);
	}

	function select(index, scroll) {
		const d = build();
		state.selected = index;
		const items = d.list.querySelectorAll(".nxt-cp-item");
		items.forEach((item, i) => {
			const on = i === index;
			item.classList.toggle("is-selected", on);
			item.setAttribute("aria-selected", on ? "true" : "false");
			if (on) {
				d.input.setAttribute("aria-activedescendant", item.id);
				if (scroll !== false && typeof item.scrollIntoView === "function") {
					item.scrollIntoView({ block: "nearest" });
				}
			}
		});
		if (!items.length) d.input.removeAttribute("aria-activedescendant");
	}

	function move(delta) {
		const n = state.visible.length;
		if (!n) return;
		select((state.selected + delta + n) % n, true);
	}

	function runAt(index) {
		const row = state.visible[index];
		if (!row) return;
		// Close first: the command may navigate, and focus should already be
		// back where it was before the route changes under it.
		close();
		try {
			const r = row.cmd.run();
			if (r && typeof r.catch === "function") {
				r.catch((err) => {
					if (window.console) console.error("Command palette:", err);
				});
			}
		} catch (err) {
			if (window.console) console.error("Command palette:", err);
		}
	}

	// ------------------------------------------------------------------
	// Server search
	// ------------------------------------------------------------------

	function scheduleSearch() {
		if (searchTimer) clearTimeout(searchTimer);
		searchTimer = null;
		const query = state.query.trim();
		if (query.length < SEARCH_MIN_CHARS) {
			state.searching = false;
			state.searchFor = null;
			state.searchResults = [];
			return;
		}
		if (state.searchFor === query) return;
		searchTimer = setTimeout(() => {
			searchTimer = null;
			runSearch(query);
		}, SEARCH_DEBOUNCE_MS);
	}

	function runSearch(query) {
		if (!(window.frappe && typeof frappe.call === "function")) return;
		const id = ++searchSeq;
		state.searching = true;
		render();
		frappe
			.call({
				method: "frappe.utils.global_search.search",
				args: { text: query, limit: 10 },
			})
			.then((r) => {
				// A reply that is not for the latest request, or not for what
				// is in the box now, is dropped on the floor.
				if (id !== searchSeq || !state.open) return;
				state.searching = false;
				if (state.query.trim() !== query) return;
				state.searchFor = query;
				state.searchResults = ((r && r.message) || []).slice(0, 10).map((row) => {
					const doctype = String(row.doctype || "");
					const name = String(row.name || "");
					const title = row.title ? String(row.title) : "";
					return {
						group: "search",
						label: title || name,
						hint: title && title !== name ? T(doctype) + " · " + name : T(doctype),
						keywords: [doctype, name],
						run: () => setRoute("Form", doctype, name),
					};
				});
				render();
			})
			.catch(() => {
				if (id !== searchSeq) return;
				state.searching = false;
				state.searchFor = query;
				state.searchResults = [];
				if (state.open) render();
			});
	}

	// ------------------------------------------------------------------
	// Events
	// ------------------------------------------------------------------

	function onInput() {
		state.query = dom.input.value;
		state.selected = 0;
		if (state.searchFor !== state.query.trim()) {
			state.searchFor = null;
			state.searchResults = [];
		}
		scheduleSearch();
		render();
	}

	function onKeyDown(e) {
		const key = e.key;
		const mod = e.ctrlKey || e.metaKey;
		if (key === "Escape" || key === "Esc") {
			e.preventDefault();
			e.stopPropagation();
			close();
			return;
		}
		if (key === "ArrowDown") {
			e.preventDefault();
			e.stopPropagation();
			move(1);
			return;
		}
		if (key === "ArrowUp") {
			e.preventDefault();
			e.stopPropagation();
			move(-1);
			return;
		}
		if (key === "Enter") {
			e.preventDefault();
			e.stopPropagation();
			runAt(state.selected);
			return;
		}
		if (key === "Tab") {
			// Focus stays on the input while the palette is up.
			e.preventDefault();
			e.stopPropagation();
			return;
		}
		if (mod && !e.altKey && typeof key === "string") {
			const k = key.toLowerCase();
			if ((k === "k" && !e.shiftKey) || (k === "p" && e.shiftKey)) {
				e.preventDefault();
				e.stopPropagation();
				close();
				return;
			}
		}
		// Anything else is typing. It stops here so Frappe's global
		// shortcuts (Ctrl+S and friends) do not fire underneath the palette.
		e.stopPropagation();
	}

	function onFocusIn(e) {
		if (!state.open || !dom) return;
		if (!dom.panel.contains(e.target)) dom.input.focus();
	}

	// ------------------------------------------------------------------
	// Open / close
	// ------------------------------------------------------------------

	function open() {
		const d = build();
		if (state.open) {
			d.input.focus();
			return;
		}
		state.open = true;
		state.query = "";
		state.selected = 0;
		state.searchFor = null;
		state.searchResults = [];
		state.searching = false;
		state.restoreFocus = document.activeElement;
		state.commands = collectCommands();
		d.input.value = "";
		d.overlay.hidden = false;
		document.documentElement.classList.add("nxt-cp-open");
		document.addEventListener("focusin", onFocusIn, true);
		render();
		d.input.focus();
		// The theme list comes from the server; when it lands the "Switch
		// theme" rows join the list without disturbing what was typed.
		loadThemes(() => {
			if (!state.open) return;
			state.commands = collectCommands();
			render();
		});
	}

	function close() {
		if (!state.open) return;
		state.open = false;
		if (searchTimer) clearTimeout(searchTimer);
		searchTimer = null;
		searchSeq++;
		document.removeEventListener("focusin", onFocusIn, true);
		document.documentElement.classList.remove("nxt-cp-open");
		if (dom) {
			dom.overlay.hidden = true;
			dom.input.value = "";
		}
		const back = state.restoreFocus;
		state.restoreFocus = null;
		if (back && typeof back.focus === "function" && document.contains(back)) {
			try {
				back.focus({ preventScroll: true });
			} catch (_e) {
				/* an element that cannot take focus any more */
			}
		}
	}

	function toggle() {
		if (state.open) close();
		else open();
	}

	// ------------------------------------------------------------------
	// Shortcuts
	// ------------------------------------------------------------------

	function bindShortcuts() {
		const keys = window.frappe && frappe.ui && frappe.ui.keys;
		if (keys && typeof keys.add_shortcut === "function") {
			// add_shortcut() removes every handler the key already has, which
			// on Frappe 16 is the awesomebar's; the entry in the shortcut
			// help dialog (Shift+/) is replaced the same way.
			["ctrl+k", "shift+ctrl+p"].forEach((shortcut) => {
				keys.add_shortcut({
					shortcut,
					action: () => {
						toggle();
						return true;
					},
					description: T("Open command palette"),
					ignore_inputs: true,
				});
			});
			return;
		}
		// No frappe.ui.keys (a page outside the Desk): listen directly.
		window.addEventListener("keydown", (e) => {
			if (!(e.ctrlKey || e.metaKey) || e.altKey || typeof e.key !== "string") return;
			const k = e.key.toLowerCase();
			if ((k === "k" && !e.shiftKey) || (k === "p" && e.shiftKey)) {
				e.preventDefault();
				toggle();
			}
		});
	}

	function whenReady(fn) {
		if (window.frappe && frappe.ui && frappe.ui.keys) {
			fn();
		} else if (window.frappe && typeof frappe.ready === "function") {
			frappe.ready(fn);
		} else if (document.readyState === "loading") {
			document.addEventListener("DOMContentLoaded", fn, { once: true });
		} else {
			fn();
		}
	}

	// ------------------------------------------------------------------
	// Public API
	// ------------------------------------------------------------------

	const api = {
		open,
		close,
		toggle,
		isOpen: () => state.open,
		/**
		 * Add a command from elsewhere. `command` is
		 * { label, run, hint?, keywords?, group?, when? }; the group defaults
		 * to "actions". Returns a function that removes it again.
		 */
		register(command) {
			if (
				!command ||
				typeof command.label !== "string" ||
				typeof command.run !== "function"
			) {
				throw new Error("NexusCommandPalette.register needs { label, run }");
			}
			const id = ++extraSeq;
			const stored = Object.assign({ group: "actions" }, command);
			if (!GROUPS.some((g) => g.key === stored.group)) stored.group = "actions";
			extras.set(id, stored);
			if (state.open) {
				state.commands = collectCommands();
				render();
			}
			return () => {
				extras.delete(id);
				if (state.open) {
					state.commands = collectCommands();
					render();
				}
			};
		},
		// The matcher, for anything that wants the same ranking.
		fuzzyMatch,
	};

	window.NexusCommandPalette = api;
	window.openCommandPalette = open;

	whenReady(bindShortcuts);
})();
