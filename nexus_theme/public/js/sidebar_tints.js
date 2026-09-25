(function () {
	"use strict";

	// Module icon tints: every sidebar item gets a colour of its own, picked
	// from what it is — Accounting blue, Selling green, Buying orange — so
	// the eye finds a module by colour before it reads the label.
	//
	// This file only tags items with `data-nx-tint="<key>"`; the colours
	// live in sidebar_skin.bundle.css, drawn only while ThemeManager has set
	// html[data-icon-tints="1"] for a theme with the switch on. With it off
	// (the default, and always on Frappe's own look) nothing is tagged and
	// the CSS matches nothing.
	//
	// Frappe v16: items of the left sidebar (.body-sidebar), which lists the
	// current workspace's links. Frappe v15: the workspace list in the
	// desk sidebar (.desk-sidebar). Both use .standard-sidebar-item with a
	// .sidebar-item-label and an .sidebar-item-icon inside.
	const ROOT = document.documentElement;
	const ATTR = "data-nx-tint";
	const ITEM_SELECTOR = [
		".body-sidebar .sidebar-items .standard-sidebar-item",
		".desk-sidebar .standard-sidebar-item",
	].join(",");

	// Checked in order; the first rule with a matching word wins. Selling
	// and Buying come before Accounting so "Sales Invoice" reads as Selling
	// rather than as an accounting document. Words are matched whole, on the
	// label and on the item's route and icon name.
	const RULES = [
		["selling", ["selling", "sales", "sell", "customer", "customers", "quotation", "pos"]],
		["buying", ["buying", "purchase", "purchasing", "buy", "supplier", "suppliers"]],
		["crm", ["crm", "lead", "leads", "opportunity", "opportunities", "prospect", "campaign"]],
		["stock", ["stock", "inventory", "warehouse", "warehouses", "item", "items", "delivery"]],
		["manufacturing", ["manufacturing", "bom", "production", "workstation", "job"]],
		[
			"accounting",
			[
				"accounting",
				"accounts",
				"account",
				"ledger",
				"journal",
				"payment",
				"payments",
				"invoice",
				"invoicing",
				"finance",
				"financial",
				"banking",
				"tax",
				"taxes",
				"budget",
			],
		],
		[
			"hr",
			[
				"hr",
				"hrms",
				"employee",
				"employees",
				"payroll",
				"leave",
				"attendance",
				"recruitment",
				"people",
				"salary",
				"expense",
				"expenses",
			],
		],
		["projects", ["projects", "project", "task", "tasks", "timesheet", "timesheets"]],
		["assets", ["assets", "asset", "maintenance"]],
		["quality", ["quality", "inspection"]],
		["support", ["support", "issue", "issues", "helpdesk", "ticket", "tickets", "warranty"]],
		["website", ["website", "web", "blog", "portal"]],
		[
			"settings",
			[
				"settings",
				"setting",
				"setup",
				"tools",
				"tool",
				"integrations",
				"customization",
				"customize",
				"users",
				"user",
				"system",
				"build",
			],
		],
	];

	// The fallback palette for anything no rule knows: a stable hash of the
	// label picks one, so the same item always gets the same colour.
	const HASH_KEYS = ["h0", "h1", "h2", "h3", "h4", "h5", "h6", "h7"];

	function words(text) {
		return String(text || "")
			.toLowerCase()
			.split(/[^a-z0-9]+/)
			.filter(Boolean);
	}

	// FNV-1a, 32-bit: tiny, fast and spreads short labels well.
	function hash(text) {
		let h = 0x811c9dc5;
		for (let i = 0; i < text.length; i++) {
			h ^= text.charCodeAt(i);
			h = Math.imul(h, 0x01000193) >>> 0;
		}
		return h;
	}

	function tintKey(label, route, icon) {
		const found = new Set(words(label).concat(words(route), words(icon)));
		for (const [key, keywords] of RULES) {
			if (keywords.some((w) => found.has(w))) return key;
		}
		const basis = String(label || route || "")
			.trim()
			.toLowerCase();
		if (!basis) return null;
		return HASH_KEYS[hash(basis) % HASH_KEYS.length];
	}

	function tagItem(el) {
		const anchor = el.querySelector("a.item-anchor, .item-anchor");
		// Section headings and spacers have no link and no icon to tint.
		if (!anchor || anchor.classList.contains("section-break")) return;
		const labelEl = el.querySelector(".sidebar-item-label");
		const iconEl = el.querySelector(".sidebar-item-icon");
		const key = tintKey(
			labelEl ? labelEl.textContent : "",
			anchor.getAttribute("href") || "",
			iconEl ? iconEl.getAttribute("item-icon") || "" : ""
		);
		if (!key) return;
		// Idempotent: writing an unchanged attribute would still wake every
		// MutationObserver on the page, ours included.
		if (el.getAttribute(ATTR) !== key) el.setAttribute(ATTR, key);
	}

	function enabled() {
		return ROOT.getAttribute("data-icon-tints") === "1";
	}

	function scan() {
		if (!enabled()) return;
		const items = document.querySelectorAll(ITEM_SELECTOR);
		for (let i = 0; i < items.length; i++) tagItem(items[i]);
	}

	// Sidebars re-render on every workspace change, and the observer below
	// sees a burst of mutations for each; one scan per frame is plenty.
	let queued = false;
	function schedule() {
		if (queued) return;
		queued = true;
		const run = () => {
			queued = false;
			scan();
		};
		if (window.requestAnimationFrame) requestAnimationFrame(run);
		else setTimeout(run, 16);
	}

	function start() {
		if (typeof MutationObserver !== "undefined") {
			// Only element additions can bring an untagged item; attribute
			// changes (ours included) are ignored, so this cannot loop.
			new MutationObserver((records) => {
				if (!enabled()) return;
				for (const rec of records) {
					if (rec.addedNodes && rec.addedNodes.length) {
						schedule();
						return;
					}
				}
			}).observe(document.body, { childList: true, subtree: true });

			// A theme with tints switched on, applied now: tag what is there.
			new MutationObserver(schedule).observe(ROOT, {
				attributes: true,
				attributeFilter: ["data-icon-tints"],
			});
		}
		if (window.frappe && frappe.router && typeof frappe.router.on === "function") {
			frappe.router.on("change", schedule);
		}
		schedule();
	}

	window.NexusSidebarTints = { tintKey, scan };

	if (document.body) start();
	else document.addEventListener("DOMContentLoaded", start);
})();
