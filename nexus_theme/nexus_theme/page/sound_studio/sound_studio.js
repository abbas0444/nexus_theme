// Launcher page for the Sound Studio dialog. The shared factory lives in
// public/js/studio_page.js, loaded via app_include_js.
frappe.pages["sound-studio"].on_page_load = function (wrapper) {
	window.nexusStudioPage(wrapper, {
		title: "Sound Studio",
		heading: "Sound Studio",
		body:
			"Choose a sound for each Desk event — save, submit, delete, notifications " +
			"and more. Use a bundled preset, upload your own, set the volume per event, " +
			"or mute everything.",
		cta: "Open Sound Studio",
		opener: "openSoundStudio",
	});
};
