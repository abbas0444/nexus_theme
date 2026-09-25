(function () {
	"use strict";

	// ------------------------------------------------------------------
	// "What's new" after an upgrade
	// ------------------------------------------------------------------
	// The server decides (whats_new.py): boot carries `nexus_theme_whats_new`
	// with `show` set when this person has not yet seen the running release
	// series, plus the notes to show. This file draws the card once the Desk
	// is ready, and tells the server when it has been dismissed so it does
	// not come back. It can also be opened on purpose, from the command
	// palette or from `window.openNexusWhatsNew()`.
	// ------------------------------------------------------------------

	const MARK_SEEN = "nexus_theme.whats_new.mark_seen";
	const GET_NOTES = "nexus_theme.whats_new.get_notes";
	// Give the Desk a moment to settle: the card should not race the
	// first page's own dialogs, and a person mid-typing should not lose
	// focus to it.
	const FIRST_SHOW_DELAY_MS = 1200;

	let openDialog = null;

	function esc(text) {
		return frappe.utils.escape_html(String(text == null ? "" : text));
	}

	function bootPayload() {
		return (window.frappe && frappe.boot && frappe.boot.nexus_theme_whats_new) || null;
	}

	function itemHTML(item) {
		const hasCommand = item.command && typeof window[item.command] === "function";
		return `
			<div class="nx-whatsnew-item">
				<div class="nx-whatsnew-item-head">${esc(item.heading)}</div>
				<div class="nx-whatsnew-item-text">${esc(item.text)}</div>
				${
					hasCommand
						? `<button type="button" class="btn btn-xs btn-default nx-whatsnew-try" data-command="${esc(
								item.command
							)}">${esc(item.command_label || __("Try it"))}</button>`
						: ""
				}
			</div>`;
	}

	function render(notes) {
		if (!notes) return "";
		return `
			<div class="nx-whatsnew">
				<div class="nx-whatsnew-summary">${esc(notes.summary)}</div>
				${(notes.items || []).map(itemHTML).join("")}
				<div class="nx-whatsnew-foot">
					${__("Version {0}", [esc(notes.version)])} ·
					<a href="https://github.com/abbas0444/nexus_theme/wiki/Release-Notes" target="_blank" rel="noopener">${__(
						"Full release notes"
					)}</a>
				</div>
			</div>`;
	}

	function markSeen(version) {
		if (!window.frappe || !frappe.call) return;
		frappe.call({ method: MARK_SEEN, args: { version }, freeze: false }).catch(() => {});
		const payload = bootPayload();
		if (payload) {
			payload.show = 0;
			payload.seen_version = version;
		}
	}

	function show(notes, opts) {
		opts = opts || {};
		if (!notes || !window.frappe || !frappe.ui || !frappe.ui.Dialog) return;
		if (openDialog) {
			openDialog.show();
			return;
		}
		const dialog = new frappe.ui.Dialog({
			title: notes.title || __("What's new"),
			size: "small",
			fields: [{ fieldtype: "HTML", fieldname: "body" }],
			primary_action_label: __("Got it"),
			primary_action: () => dialog.hide(),
		});
		dialog.$wrapper.addClass("nx-whatsnew-dialog");
		dialog.fields_dict.body.$wrapper.html(render(notes));
		dialog.$wrapper.on("click", ".nx-whatsnew-try", (e) => {
			const name = e.currentTarget.getAttribute("data-command");
			dialog.hide();
			// After the dialog's own fade-out, so the palette or studio that
			// opens does not stack on a closing modal.
			setTimeout(() => {
				if (typeof window[name] === "function") window[name]();
			}, 250);
		});
		dialog.$wrapper.on("hidden.bs.modal", () => {
			if (opts.markSeenOnClose) markSeen(notes.version);
			openDialog = null;
			// Frappe keeps a hidden dialog's wrapper in <body>; this one is
			// rebuilt from the notes whenever it is wanted again.
			dialog.$wrapper.remove();
		});
		openDialog = dialog;
		dialog.show();
	}

	/** Open the card for the running release on purpose. */
	function openNexusWhatsNew() {
		const payload = bootPayload();
		if (payload && payload.notes) {
			show(payload.notes, { markSeenOnClose: !!payload.show });
			return;
		}
		if (!window.frappe || !frappe.call) return;
		frappe
			.call({ method: GET_NOTES })
			.then((r) => {
				if (r && r.message) show(r.message, { markSeenOnClose: false });
				else
					frappe.show_alert({
						message: __("Nothing new to show for this version."),
						indicator: "blue",
					});
			})
			.catch(() => {});
	}

	function showOnFirstVisit() {
		const payload = bootPayload();
		if (!payload || !payload.show || !payload.notes) return;
		setTimeout(() => {
			// Something else may have claimed the screen meanwhile.
			if (document.querySelector(".modal.show, .modal.in")) {
				// Try again after that modal closes, once.
				$(document).one("hidden.bs.modal", () => {
					setTimeout(() => show(payload.notes, { markSeenOnClose: true }), 400);
				});
				return;
			}
			show(payload.notes, { markSeenOnClose: true });
		}, FIRST_SHOW_DELAY_MS);
	}

	function registerCommand() {
		const palette = window.NexusCommandPalette;
		if (!palette || typeof palette.register !== "function") return;
		palette.register({
			id: "nexus-whats-new",
			group: "actions",
			label: __("What's new in Nexus Theme"),
			run: openNexusWhatsNew,
		});
	}

	function boot() {
		if (window.__nexusWhatsNewBooted) return;
		window.__nexusWhatsNewBooted = true;
		window.openNexusWhatsNew = openNexusWhatsNew;
		registerCommand();
		showOnFirstVisit();
	}

	if (window.frappe && frappe.boot) {
		// app_include_js runs after boot on the Desk.
		if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
		else boot();
	} else {
		$(document).one("app_ready", boot);
	}
})();
