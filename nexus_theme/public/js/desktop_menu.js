(function () {
	"use strict";

	// ------------------------------------------------------------------
	// Entry points for Frappe v16's Desk
	// ------------------------------------------------------------------
	// v16 replaced the classic navbar with the "desktop" page, whose
	// setup_navbar() does exactly this:
	//
	//     setup_navbar() { $(".sticky-top > .navbar").hide(); }
	//
	// Navbar Settings items — where install.py registers Theme Studio and
	// Sound Settings — are rendered into that navbar, so on the new Desk they
	// exist in the database and never appear on screen. The app shipped with
	// no reachable UI entry point at all; the only way in was calling
	// openThemeSwitcher() from the browser console.
	//
	// The supported replacement is DesktopPage.add_menu_item(), which feeds
	// the avatar dropdown at the top right. Frappe's own entries occupy order
	// 10–40 and Logout is pinned last regardless of order, so Theme Studio
	// takes 21 — immediately below "Toggle Theme", its nearest neighbour in
	// meaning — and Sound Settings 22.
	//
	// The Navbar Settings registration is left in place: it is still correct
	// for the classic navbar, and add_menu_item() de-duplicates on label, so
	// the two can never produce a doubled entry.
	// ------------------------------------------------------------------

	const ITEMS = [
		{
			icon: "palette",
			label: "Theme Studio",
			order: 21,
			onClick: function () {
				if (window.openThemeSwitcher) window.openThemeSwitcher();
			},
		},
		{
			icon: "volume-2",
			label: "Sound Settings",
			order: 22,
			onClick: function () {
				if (window.openSoundStudio) window.openSoundStudio();
			},
		},
	];

	const PATCH_FLAG = "__nexus_theme_desktop_menu";
	const RETRY_MS = 300;
	const MAX_TRIES = 40; // ~12s, then stop quietly rather than poll forever

	// add_menu_item() ignores a label it already holds, so this is safe to
	// call on every page show. Returns true if anything was actually added.
	function addItems(page) {
		if (!page || typeof page.add_menu_item !== "function") return false;
		const before = (page.desktop_menu_items || []).length;
		ITEMS.forEach(function (item) {
			page.add_menu_item(item);
		});
		return (page.desktop_menu_items || []).length > before;
	}

	function patch() {
		const pages = window.frappe && frappe.pages;
		const desktop = pages && pages["desktop"];
		if (!desktop) return false;

		// Wait for desktop.js to have installed its own handlers. Patching the
		// empty shell the page loader creates would just be overwritten when
		// that file finally assigns on_page_load / on_page_show.
		if (typeof desktop.on_page_show !== "function") return false;
		if (desktop[PATCH_FLAG]) return true;
		desktop[PATCH_FLAG] = true;

		// Preferred path: register straight after the page object is built and
		// before anything renders, so the first setup_avatar() already includes
		// our items and no rebuild is needed.
		const originalLoad = desktop.on_page_load;
		if (typeof originalLoad === "function") {
			desktop.on_page_load = function () {
				const out = originalLoad.apply(this, arguments);
				addItems(desktop.desktop_page);
				return out;
			};
		}

		// on_page_show runs update() -> make() -> setup_avatar(), rebuilding the
		// dropdown from desktop_menu_items. Registering just before it keeps us
		// present across navigation without calling setup_avatar() ourselves.
		const originalShow = desktop.on_page_show;
		desktop.on_page_show = function () {
			addItems(desktop.desktop_page);
			return originalShow.apply(this, arguments);
		};

		// Fallback for the common case: this script is an app_include_js bundle,
		// so it runs before the desktop page is fetched, and by the time polling
		// finds it the avatar menu is usually already on screen. Rebuild once so
		// the items appear without making the user navigate away and back.
		//
		// frappe.ui.create_menu() is not idempotent — each call registers a new
		// menu instance and a document click listener — which is why this runs
		// only when addItems() reports something new, and only once per load.
		if (desktop.desktop_page && addItems(desktop.desktop_page)) {
			try {
				desktop.desktop_page.setup_avatar();
			} catch (_e) {
				/* the wrapped on_page_show will pick it up on the next visit */
			}
		}
		return true;
	}

	let tries = 0;
	(function attempt() {
		if (patch()) return;
		if (++tries >= MAX_TRIES) return;
		setTimeout(attempt, RETRY_MS);
	})();
})();
