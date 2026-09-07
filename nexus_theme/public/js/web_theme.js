(function () {
	"use strict";

	// ------------------------------------------------------------------
	// Mirror the injected theme's polarity onto <html data-theme> for
	// website and login pages.
	//
	// website.py injects the theme as CSS custom properties, which covers
	// anything reading --theme-*. But a lot of website CSS — Frappe's own,
	// and stylesheets from other apps (a login logo mask, for example) —
	// is keyed off [data-theme="dark"] instead. The Desk sets that attribute
	// from the theme's is_dark flag; without the same thing here, a dark site
	// theme renders with light-mode patches on top of it.
	//
	// The polarity is read back from the `color-scheme` declaration in that
	// injected block, so there is nothing extra to serve and no way for the
	// two to disagree.
	//
	// Runs from <head>, after the injected <style>, so the attribute is set
	// before the body paints.
	// ------------------------------------------------------------------

	try {
		var root = document.documentElement;

		// An explicit choice — Frappe's own toggle, or another app — wins.
		if (root.getAttribute("data-theme")) return;

		var scheme = window
			.getComputedStyle(root)
			.getPropertyValue("color-scheme")
			.trim()
			.toLowerCase();

		if (scheme === "dark" || scheme === "light") {
			root.setAttribute("data-theme", scheme);
		}
	} catch (_e) {
		/* never block page rendering over a cosmetic attribute */
	}
})();
