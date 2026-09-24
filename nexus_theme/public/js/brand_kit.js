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

	// Where Frappe draws the app logo, per Desk:
	//
	//   v16  desk/page/desktop/desktop.html — <img id="brand-logo"> in the
	//        desktop navbar's `.navbar-home`. The page body is emptied and
	//        re-rendered by DesktopPage.make() on every visit home, so the
	//        element is replaced, not just re-shown.
	//   v16  ui/sidebar/sidebar_header.html — the workspace icon in the
	//        sidebar header. Usually a Desktop Icon of its own; only when a
	//        workspace has none does SidebarHeader fall back to the app logo
	//        (get_default_icon → frappe.boot.app_data[0].app_logo_url). That
	//        fallback is the brand, so it is swapped; a real workspace icon is
	//        not ours to touch. The header is removed and rebuilt on every
	//        workspace change.
	//   v15  the classic navbar's `.navbar-brand img` / `.app-logo`.
	//
	// The old selector list targeted only the v15 shapes, so on v16 it found
	// nothing in its 40 tries and gave up.
	const LOGO_SELECTORS = [
		".desktop-navbar .navbar-home img",
		"#brand-logo",
		".navbar-brand img",
		".navbar-brand .app-logo",
	];
	const SIDEBAR_LOGO = ".sidebar-header .header-logo img";

	function appLogoUrls() {
		const boot = window.frappe && frappe.boot;
		const urls = [];
		if (!boot) return urls;
		if (boot.app_logo_url) urls.push(boot.app_logo_url);
		for (const app of boot.app_data || []) {
			if (app && app.app_logo_url) urls.push(app.app_logo_url);
		}
		return urls;
	}

	function swap(img, src) {
		if (img.getAttribute("src") === src) return;
		img.setAttribute("src", src);
		img.removeAttribute("srcset");
	}

	/** Idempotent: re-run as often as the Desk re-renders. */
	function applyNavbarLogo(url) {
		const src = safeAssetUrl(url);
		if (!src) return;
		document.querySelectorAll(LOGO_SELECTORS.join(", ")).forEach((img) => swap(img, src));

		const fallbacks = appLogoUrls();
		document.querySelectorAll(SIDEBAR_LOGO).forEach((img) => {
			const current = img.getAttribute("src") || "";
			if (current === src || fallbacks.includes(current)) swap(img, src);
		});
	}

	// The logo elements come and go with navigation, so one pass at boot is
	// never enough. Re-apply on the events Frappe fires when it rebuilds
	// them — "desktop_screen" after every desktop render, "page-change" on
	// every navigation — and, because the sidebar header rebuilds on its own
	// schedule, on any DOM insertion as well. The observer is coalesced to
	// one pass per frame, and a pass on an unchanged page is a handful of
	// querySelectorAll calls that write nothing, so this costs nothing
	// noticeable. Setting `src` is an attribute change on an existing node,
	// which a childList observer does not see, so it cannot loop.
	function keepLogoApplied(url) {
		applyNavbarLogo(url);

		if (window.$ && typeof $(document).on === "function") {
			$(document).on("desktop_screen page-change", () => applyNavbarLogo(url));
		}

		if (typeof MutationObserver === "undefined" || !document.body) return;
		let scheduled = false;
		const observer = new MutationObserver(() => {
			if (scheduled) return;
			scheduled = true;
			requestAnimationFrame(() => {
				scheduled = false;
				applyNavbarLogo(url);
			});
		});
		observer.observe(document.body, { childList: true, subtree: true });
	}

	function boot() {
		const s = settings();
		if (!s) return;

		applyFavicon(s.favicon);

		if (!s.navbar_logo || !safeAssetUrl(s.navbar_logo)) return;
		keepLogoApplied(s.navbar_logo);
	}

	if (window.frappe && typeof frappe.ready === "function") {
		frappe.ready(boot);
	} else if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", boot);
	} else {
		boot();
	}
})();
