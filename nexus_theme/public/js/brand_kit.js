(function () {
	"use strict";

	// ------------------------------------------------------------------
	// Brand kit: swap the navbar logo and the favicon for the ones set in
	// Theme Settings. Both arrive in bootinfo (api.extend_boot_session), so
	// there is no extra round-trip and nothing runs on sites that have not
	// configured a brand.
	// ------------------------------------------------------------------

	function settings() {
		return (window.frappe && frappe.boot && frappe.boot.nexus_theme_settings) || null;
	}

	/** Only same-origin paths — never point the page at a third-party host. */
	function safeAssetUrl(url) {
		if (typeof url !== "string" || !url) return null;
		const v = url.trim();
		return v.startsWith("/") && !v.startsWith("//") ? v : null;
	}

	function applyFavicon(url) {
		const href = safeAssetUrl(url);
		if (!href) return;
		let link = document.querySelector("link[rel~='icon']");
		if (!link) {
			link = document.createElement("link");
			link.rel = "icon";
			document.head.appendChild(link);
		}
		if (link.getAttribute("href") !== href) link.setAttribute("href", href);
	}

	function applyNavbarLogo(url) {
		const src = safeAssetUrl(url);
		if (!src) return false;
		// Frappe renders the navbar brand differently across versions; cover the
		// common shapes rather than betting on one.
		const img = document.querySelector(
			".navbar-brand img, .app-logo, .navbar .navbar-home img, .sidebar-standard-icons img"
		);
		if (!img) return false;
		if (img.getAttribute("src") !== src) {
			img.setAttribute("src", src);
			img.removeAttribute("srcset");
		}
		return true;
	}

	function boot() {
		const s = settings();
		if (!s) return;

		applyFavicon(s.favicon);

		if (!s.navbar_logo) return;
		// The navbar is rendered asynchronously; retry briefly, then give up
		// rather than polling for the life of the page.
		let attempts = 0;
		const tryLogo = () => {
			if (applyNavbarLogo(s.navbar_logo)) return;
			if (attempts++ < 40) setTimeout(tryLogo, 250);
		};
		tryLogo();
	}

	if (window.frappe && typeof frappe.ready === "function") {
		frappe.ready(boot);
	} else if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", boot);
	} else {
		boot();
	}
})();
