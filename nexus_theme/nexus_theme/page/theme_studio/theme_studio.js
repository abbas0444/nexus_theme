// Launcher page for the Theme Studio dialog. The shared factory lives in
// public/js/studio_page.js, loaded via app_include_js.
frappe.pages["theme-studio"].on_page_load = function (wrapper) {
	window.nexusStudioPage(wrapper, {
		title: "Theme Studio",
		heading: "Theme Studio",
		body:
			"Pick from the bundled themes, fill every colour from a curated palette, " +
			"or generate a whole palette from one brand colour — then fine-tune and " +
			"save it as your own.",
		cta: "Open Theme Studio",
		opener: "openThemeSwitcher",
	});
};
