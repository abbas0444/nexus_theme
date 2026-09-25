// Nexus Home — the optional landing page of the Desk (/app/nexus-home).
//
// A greeting, three shortcuts and one tile per workspace the person can
// already open. When "Use the Nexus Home Page" is ticked in Theme Settings,
// boot points frappe.boot.home_page here (api._apply_home_boot), which is
// what both Desk routers open for an empty route. The page is reachable at
// its own address either way.
//
// Everything the server sends is data, never markup: names and labels go
// in through textContent, routes are built here from names, and an icon is
// only drawn when its name is a plain identifier that exists in the Desk's
// own icon sprite.
(function () {
	"use strict";

	const PAGE = "nexus-home";
	// Slots in the tint palette in nexus_home.css; utils/home.TINT_COUNT
	// holds the same number.
	const TINTS = 8;
	const ICON_NAME = /^[a-z0-9][a-z0-9_-]*$/i;

	// ------------------------------------------------------------------
	// Small helpers
	// ------------------------------------------------------------------

	function el(tag, cls, text) {
		const node = document.createElement(tag);
		if (cls) node.className = cls;
		if (text != null) node.textContent = text;
		return node;
	}

	function homeBoot() {
		return (frappe.boot && frappe.boot.nexus_home) || {};
	}

	function settingsFrom(server) {
		return Object.assign(
			{ show_greeting: 1, show_shortcuts: 1, layout: "grid" },
			homeBoot(),
			server || {}
		);
	}

	function slug(text) {
		if (frappe.router && typeof frappe.router.slug === "function") {
			return frappe.router.slug(text);
		}
		return String(text || "")
			.toLowerCase()
			.replace(/ /g, "-");
	}

	// "/app/…" on Frappe 15, "/desk/…" on Frappe 16: make_url knows which.
	// Anchors with these hrefs are picked up by the Desk's own link handler,
	// so a click routes in place and a middle-click opens a tab.
	function deskUrl(parts) {
		if (frappe.router && typeof frappe.router.make_url === "function") {
			return frappe.router.make_url(parts);
		}
		return "/app/" + parts.map((p) => encodeURIComponent(String(p))).join("/");
	}

	// Same 31-multiplier, 32-bit string hash as utils/home.tint_index, used
	// when a tile arrives without a tint (the boot fallback below).
	function tintIndex(name) {
		let h = 0;
		for (const ch of String(name || "")) {
			h = (Math.imul(h, 31) + ch.codePointAt(0)) >>> 0;
		}
		return h % TINTS;
	}

	// The same hour boundaries as utils/home.greeting_bucket.
	function greetingFor(date, name) {
		const h = date.getHours();
		if (h >= 5 && h < 12) return __("Good morning, {0}", [name]);
		if (h >= 12 && h < 18) return __("Good afternoon, {0}", [name]);
		return __("Good evening, {0}", [name]);
	}

	function todayLabel(date) {
		try {
			const lang = (frappe.boot && frappe.boot.lang) || undefined;
			return date.toLocaleDateString(lang, {
				weekday: "long",
				day: "numeric",
				month: "long",
			});
		} catch (_e) {
			return "";
		}
	}

	function firstNameFromBoot() {
		const info = (frappe.boot && frappe.boot.user_info) || {};
		const me = info[frappe.session.user] || {};
		const full = String(me.fullname || frappe.session.user_fullname || "").trim();
		return full.split(/\s+/)[0] || String(frappe.session.user || "").split("@")[0];
	}

	// ------------------------------------------------------------------
	// Tile routes and icons
	// ------------------------------------------------------------------

	function tileHref(tile) {
		if (tile.type === "URL") {
			const link = String(tile.external_link || "").trim();
			return /^(https?:\/\/|\/(?!\/))/i.test(link) ? link : null;
		}
		if (
			tile.type === "Link" &&
			tile.link_to &&
			typeof frappe.utils.generate_route === "function"
		) {
			try {
				const report = tile.report || {};
				return frappe.utils.generate_route({
					type: tile.link_type || "DocType",
					name: tile.link_to,
					is_query_report:
						report.report_type === "Query Report" ||
						report.report_type === "Script Report",
					report_ref_doctype: report.ref_doctype,
				});
			} catch (_e) {
				// Fall through to the workspace itself.
			}
		}
		if (!tile.public) return deskUrl(["private", slug(tile.title || tile.name)]);
		return deskUrl([slug(tile.name)]);
	}

	// `names` is one icon name or a list tried in order — the two Desks
	// ship different sprites (Frappe 16 adds Lucide: "bell", "plus"; Frappe
	// 15 has only its own set: "notification", "add").
	function iconMarkup(names) {
		if (typeof frappe.utils.icon !== "function") return null;
		for (const name of [].concat(names || [])) {
			const icon = String(name || "");
			if (!ICON_NAME.test(icon)) continue;
			// frappe.utils.icon() draws an empty <svg> for a name the sprite
			// does not have; a letter avatar reads better than a blank square.
			const id = icon.startsWith("es-") ? icon : "icon-" + icon;
			if (document.getElementById(id)) return frappe.utils.icon(icon, "md");
		}
		return null;
	}

	function avatarLetter(label) {
		const first = Array.from(String(label || "").trim())[0] || "?";
		return first.toLocaleUpperCase();
	}

	// ------------------------------------------------------------------
	// Tiles from boot, for when the server call fails
	// ------------------------------------------------------------------
	// Frappe already sends the workspaces this user may open: Frappe 16 as
	// boot.workspaces.pages, Frappe 15 as boot.allowed_workspaces. Same
	// source as the server's, minus the to-do counts.

	function tilesFromBoot() {
		const b = frappe.boot || {};
		const pages =
			(b.workspaces && Array.isArray(b.workspaces.pages) && b.workspaces.pages) ||
			(Array.isArray(b.allowed_workspaces) && b.allowed_workspaces) ||
			[];
		const seen = new Set();
		const user = frappe.session.user;
		return pages
			.filter((p) => {
				if (!p || !p.name || seen.has(p.name) || p.is_hidden || p.parent_page)
					return false;
				if (!p.public && p.for_user && p.for_user !== user) return false;
				seen.add(p.name);
				return true;
			})
			.map((p) => ({
				name: p.name,
				title: p.title || p.name,
				label: p.label || __(p.title || p.name),
				public: p.public ? 1 : 0,
				icon: p.icon || null,
				count: 0,
				tint: tintIndex(p.name),
				type: p.type || "Workspace",
				link_type: p.link_type,
				link_to: p.link_to,
				external_link: p.external_link,
				report: p.report,
			}));
	}

	// ------------------------------------------------------------------
	// Shortcuts
	// ------------------------------------------------------------------

	// Create New: the command palette already lists "New <DocType>" for
	// every DocType this user can create, so open it with "new " typed in.
	// Without the palette, a small picker over boot.user.can_create.
	function openCreateNew() {
		const palette = window.NexusCommandPalette;
		if (palette && typeof palette.open === "function") {
			palette.open();
			const input = document.querySelector(".nxt-cp-input");
			if (input) {
				input.value = "new ";
				input.dispatchEvent(new Event("input", { bubbles: true }));
				try {
					input.setSelectionRange(input.value.length, input.value.length);
				} catch (_e) {
					/* not a text input any more */
				}
				return;
			}
			if (typeof palette.close === "function") palette.close();
		}
		openCreatePicker();
	}

	function openCreatePicker() {
		const creatable = ((frappe.boot.user && frappe.boot.user.can_create) || [])
			.filter((dt) => !(frappe.model.is_single && frappe.model.is_single(dt)))
			.map((dt) => ({ value: dt, label: __(dt) }))
			.sort((a, b) => a.label.localeCompare(b.label));

		if (!creatable.length) {
			frappe.show_alert({
				message: __("You cannot create any documents."),
				indicator: "orange",
			});
			return;
		}

		const dialog = new frappe.ui.Dialog({
			title: __("Create New"),
			fields: [
				{
					fieldname: "doctype",
					fieldtype: "Autocomplete",
					label: __("Document Type"),
					options: creatable,
					reqd: 1,
				},
			],
			primary_action_label: __("Create"),
			primary_action(values) {
				const dt = values && values.doctype;
				if (!creatable.some((c) => c.value === dt)) return;
				dialog.hide();
				frappe.new_doc(dt);
			},
		});
		dialog.show();
	}

	// Notifications: open Frappe's own panel through its own button — the
	// sidebar's bell on Frappe 16, the navbar's on Frappe 15 — when that
	// button is on screen; otherwise go to the Notification Log list.
	function openNotifications() {
		// Deferred so this click has finished bubbling first: Frappe closes
		// the panel on any document click outside its button.
		setTimeout(() => {
			const candidates = [
				".standard-items-sections .sidebar-notification:not(.hidden)",
				".navbar .dropdown-notifications:not(.hidden) .notifications-icon",
			];
			for (const selector of candidates) {
				const button = document.querySelector(selector);
				if (button && onScreen(button)) {
					button.click();
					return;
				}
			}
			frappe.set_route("List", "Notification Log");
		}, 0);
	}

	function onScreen(node) {
		const rect = node.getBoundingClientRect();
		return (
			rect.width > 0 &&
			rect.height > 0 &&
			rect.right > 0 &&
			rect.left < window.innerWidth &&
			rect.bottom > 0 &&
			rect.top < window.innerHeight
		);
	}

	// ------------------------------------------------------------------
	// Page
	// ------------------------------------------------------------------

	class NexusHome {
		constructor(wrapper) {
			this.wrapper = wrapper;
			this.page = frappe.ui.make_app_page({
				parent: wrapper,
				title: __("Home"),
				single_column: true,
			});
			this.data = null;
			this.seq = 0;
			this.build();
		}

		build() {
			const root = el("div", "nxh");
			root.setAttribute("data-layout", "grid");

			// Greeting
			const hero = el("header", "nxh-hero");
			this.greeting = el("h2", "nxh-greeting");
			this.subtitle = el(
				"p",
				"nxh-subtitle",
				__("Here's what's happening in your workspace today.")
			);
			this.date = el("p", "nxh-date");
			hero.append(this.date, this.greeting, this.subtitle);

			// Shortcuts
			const shortcuts = el("section", "nxh-card nxh-shortcuts");
			shortcuts.setAttribute("aria-labelledby", "nxh-shortcuts-title");
			const scTitle = el("h3", "nxh-card-title", __("Shortcuts"));
			scTitle.id = "nxh-shortcuts-title";
			const scRow = el("div", "nxh-shortcut-row");
			scRow.append(
				this.shortcutButton(["plus", "add"], __("Create New"), () => openCreateNew()),
				this.shortcutLink(["file-text", "file"], __("Reports"), deskUrl(["report"]), () =>
					frappe.model.can_read("Report")
				),
				(this.notifyButton = this.shortcutButton(
					["bell", "notification"],
					__("Notifications"),
					() => openNotifications()
				))
			);
			shortcuts.append(scTitle, scRow);

			// Tiles
			const apps = el("section", "nxh-apps");
			apps.setAttribute("aria-labelledby", "nxh-apps-title");
			const head = el("div", "nxh-apps-head");
			const appsTitle = el("h3", "nxh-card-title", __("Your workspaces"));
			appsTitle.id = "nxh-apps-title";
			head.append(appsTitle);
			// Frappe 16's own Desktop (the app icon grid) is still one click
			// away when this page has taken its place.
			if (homeBoot().frappe_home === "desktop") {
				const all = el("a", "nxh-apps-all", __("All apps"));
				all.href = deskUrl(["desktop"]);
				head.append(all);
			}
			this.tiles = el("ul", "nxh-tiles");
			this.tiles.setAttribute("role", "list");
			this.empty = el("p", "nxh-empty", __("There are no workspaces to show yet."));
			this.empty.hidden = true;
			apps.append(head, this.tiles, this.empty);

			root.append(hero, shortcuts, apps);
			this.root = root;
			this.hero = hero;
			this.shortcuts = shortcuts;

			const body = this.wrapper.querySelector(".page-content") || this.wrapper;
			body.append(root);
			this.renderSkeleton();
		}

		shortcutButton(icon, label, onClick) {
			const button = el("button", "nxh-shortcut");
			button.type = "button";
			this.fillShortcut(button, icon, label);
			button.addEventListener("click", onClick);
			return button;
		}

		shortcutLink(icon, label, href, allowed) {
			const link = el("a", "nxh-shortcut");
			link.href = href;
			this.fillShortcut(link, icon, label);
			if (allowed && !allowed()) link.hidden = true;
			return link;
		}

		fillShortcut(node, icon, label) {
			const art = el("span", "nxh-shortcut-icon");
			art.setAttribute("aria-hidden", "true");
			const markup = iconMarkup(icon);
			if (markup) art.innerHTML = markup;
			const text = el("span", "nxh-shortcut-label", label);
			const badge = el("span", "nxh-badge");
			badge.hidden = true;
			node.append(art, text, badge);
		}

		applySettings(settings) {
			this.root.setAttribute("data-layout", settings.layout === "list" ? "list" : "grid");
			this.hero.hidden = !settings.show_greeting;
			this.shortcuts.hidden = !settings.show_shortcuts;
		}

		greet(name) {
			const now = new Date();
			this.greeting.textContent = greetingFor(now, name || firstNameFromBoot());
			this.date.textContent = todayLabel(now);
		}

		renderSkeleton() {
			this.tiles.setAttribute("aria-busy", "true");
			this.tiles.replaceChildren();
			for (let i = 0; i < 8; i++) {
				const li = el("li", "nxh-tile-slot");
				li.append(el("span", "nxh-tile nxh-tile-skeleton"));
				this.tiles.append(li);
			}
		}

		renderTiles(tiles) {
			this.tiles.removeAttribute("aria-busy");
			this.tiles.replaceChildren();
			(tiles || []).forEach((tile) => {
				const href = tileHref(tile);
				if (!href) return;
				const li = el("li", "nxh-tile-slot");
				const a = el("a", "nxh-tile");
				a.href = href;
				if (tile.type === "URL" && /^https?:/i.test(href)) {
					a.target = "_blank";
					a.rel = "noopener noreferrer";
				}
				const tint = Number.isInteger(tile.tint)
					? tile.tint % TINTS
					: tintIndex(tile.name);
				a.classList.add("nxh-tint-" + tint);

				const art = el("span", "nxh-tile-icon");
				art.setAttribute("aria-hidden", "true");
				const markup = iconMarkup(tile.icon);
				if (markup) {
					art.innerHTML = markup;
				} else {
					art.classList.add("nxh-tile-letter");
					art.textContent = avatarLetter(tile.label);
				}

				const label = el("span", "nxh-tile-label", tile.label || tile.name);
				a.append(art, label);

				const count = parseInt(tile.count, 10) || 0;
				if (count > 0) {
					const badge = el("span", "nxh-badge", count > 99 ? "99+" : String(count));
					badge.title = __("{0} open to-dos assigned to you", [count]);
					a.append(badge);
					a.setAttribute(
						"aria-label",
						__("{0}, {1} open to-dos assigned to you", [
							tile.label || tile.name,
							count,
						])
					);
				}
				li.append(a);
				this.tiles.append(li);
			});
			this.empty.hidden = this.tiles.children.length > 0;
		}

		setNotificationCount(n) {
			const badge = this.notifyButton && this.notifyButton.querySelector(".nxh-badge");
			if (!badge) return;
			const count = parseInt(n, 10) || 0;
			badge.hidden = count <= 0;
			badge.textContent = count > 99 ? "99+" : String(count);
		}

		refresh() {
			// Settings from boot first, so the layout is right before the
			// call returns; the call's own copy (fresher) follows.
			this.applySettings(settingsFrom(this.data && this.data.settings));
			this.greet(this.data && this.data.greeting_name);
			if (this.data) {
				this.renderTiles(this.data.tiles);
			}
			this.setNotificationCount(
				this.data ? this.data.unread_notifications : frappe.boot.notification_unread_count
			);

			const seq = ++this.seq;
			frappe
				.xcall("nexus_theme.api.get_home_data")
				.then((data) => {
					if (seq !== this.seq || !data) return;
					if (!Array.isArray(data.tiles) || !data.tiles.length) {
						data.tiles = tilesFromBoot();
					}
					this.data = data;
					this.applySettings(settingsFrom(data.settings));
					this.greet(data.greeting_name);
					this.renderTiles(data.tiles);
					this.setNotificationCount(data.unread_notifications);
				})
				.catch(() => {
					if (seq !== this.seq) return;
					if (!this.data) this.renderTiles(tilesFromBoot());
				});
		}
	}

	frappe.pages[PAGE].on_page_load = function (wrapper) {
		wrapper.nexusHome = new NexusHome(wrapper);
	};

	// Every arrival, not only the first: the greeting follows the clock and
	// the counts follow the person's to-dos.
	frappe.pages[PAGE].on_page_show = function (wrapper) {
		if (wrapper.nexusHome) wrapper.nexusHome.refresh();
	};
})();
