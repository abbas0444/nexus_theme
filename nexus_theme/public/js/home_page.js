(function () {
	"use strict";

	// ------------------------------------------------------------------
	// Nexus Home: entry points outside the page itself
	// ------------------------------------------------------------------
	// The page (nexus_theme/page/nexus_home) only loads when someone opens
	// it, so anything that has to exist on every Desk page lives here:
	// window.openNexusHome(), and an "Open Home" command in the palette
	// while the page is switched on in Theme Settings. With the setting
	// off nothing is registered, so an untouched site looks as before.
	// ------------------------------------------------------------------

	function homeBoot() {
		return (window.frappe && frappe.boot && frappe.boot.nexus_home) || {};
	}

	function openNexusHome() {
		frappe.set_route(homeBoot().page || "nexus-home");
	}

	function registerCommand() {
		if (!homeBoot().enabled) return;
		const palette = window.NexusCommandPalette;
		if (!palette || typeof palette.register !== "function") return;
		palette.register({
			id: "nexus-home",
			group: "actions",
			label: __("Open Home"),
			keywords: ["home", "start", "landing", "workspaces"],
			run: openNexusHome,
		});
	}

	function boot() {
		if (window.__nexusHomeBooted) return;
		window.__nexusHomeBooted = true;
		window.openNexusHome = openNexusHome;
		registerCommand();
	}

	if (window.frappe && frappe.boot) {
		// app_include_js runs after boot on the Desk.
		if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
		else boot();
	} else {
		$(document).one("app_ready", boot);
	}
})();
