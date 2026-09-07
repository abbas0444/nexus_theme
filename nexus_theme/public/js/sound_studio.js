(function () {
	"use strict";

	// Maps user-facing event keys to the Frappe-internal sound name used when
	// previewing. "Save" has no native Frappe sound — it piggybacks on "click".
	const PREVIEW_ALIAS = {
		save: "click",
	};

	const EVENTS = [
		{ key: "login", label: "Login" },
		{ key: "logout", label: "Logout" },
		{ key: "save", label: "Save (form click)" },
		{ key: "submit", label: "Submit" },
		{ key: "cancel", label: "Cancel" },
		{ key: "delete", label: "Delete" },
		{ key: "error", label: "Error" },
		{ key: "email", label: "Email" },
		{ key: "alert", label: "Alert" },
		{ key: "notification", label: "Notification (bell)" },
		{ key: "missing_fields", label: "Missing Fields" },
	];

	// Three built-in preset sounds per event. Each preset is just a URL the
	// existing `set_user_sound` API persists — no schema changes.
	//
	// All preset sounds are original tones synthesised by tools/generate_sounds.py
	// and bundled with the app under nexus_theme/public/sounds/, served by
	// Frappe at /assets/nexus_theme/sounds/<event>-<n>.wav. Every event has
	// three presets; preset 1 is the "apt" sound also registered as the default in
	// hooks.py. To retune them, edit the recipes in tools/generate_sounds.py and
	// re-run it — no external/licensed audio is used.
	const SND = (event, n) => `/assets/nexus_theme/sounds/${event}-${n}.wav`;

	const PRESETS = {
		login: [
			{ label: "Welcome", url: SND("login", 1) },
			{ label: "Unlock", url: SND("login", 2) },
			{ label: "Bright", url: SND("login", 3) },
		],
		logout: [
			{ label: "Sign Off", url: SND("logout", 1) },
			{ label: "Soft", url: SND("logout", 2) },
			{ label: "Power Down", url: SND("logout", 3) },
		],
		save: [
			{ label: "Pop", url: SND("save", 1) },
			{ label: "Ding", url: SND("save", 2) },
			{ label: "Chirp", url: SND("save", 3) },
		],
		submit: [
			{ label: "Success", url: SND("submit", 1) },
			{ label: "Confirm", url: SND("submit", 2) },
			{ label: "Bell", url: SND("submit", 3) },
		],
		cancel: [
			{ label: "Soft", url: SND("cancel", 1) },
			{ label: "Tick", url: SND("cancel", 2) },
			{ label: "Down", url: SND("cancel", 3) },
		],
		delete: [
			{ label: "Drop", url: SND("delete", 1) },
			{ label: "Thud", url: SND("delete", 2) },
			{ label: "Swipe", url: SND("delete", 3) },
		],
		error: [
			{ label: "Buzz", url: SND("error", 1) },
			{ label: "Alert", url: SND("error", 2) },
			{ label: "Low", url: SND("error", 3) },
		],
		email: [
			{ label: "Ding", url: SND("email", 1) },
			{ label: "Whoosh", url: SND("email", 2) },
			{ label: "Pop", url: SND("email", 3) },
		],
		alert: [
			{ label: "Chirp", url: SND("alert", 1) },
			{ label: "Pulse", url: SND("alert", 2) },
			{ label: "Ring", url: SND("alert", 3) },
		],
		click: [
			{ label: "Tick", url: SND("click", 1) },
			{ label: "Tap", url: SND("click", 2) },
			{ label: "Snap", url: SND("click", 3) },
		],
		notification: [
			{ label: "Bell", url: SND("notification", 1) },
			{ label: "Ping", url: SND("notification", 2) },
			{ label: "Pop", url: SND("notification", 3) },
		],
		missing_fields: [
			{ label: "Warn", url: SND("missing_fields", 1) },
			{ label: "Nudge", url: SND("missing_fields", 2) },
			{ label: "Buzz", url: SND("missing_fields", 3) },
		],
	};

	/**
	 * Returns the index of the currently-selected preset for an event, or -1
	 * when the saved URL is a custom upload (not in our preset list) or absent.
	 */
	function selectedPresetIndex(eventKey, savedUrl) {
		if (!savedUrl) return -1;
		const list = PRESETS[eventKey] || [];
		return list.findIndex((p) => p.url === savedUrl);
	}

	/**
	 * Lightweight one-shot audio preview for a URL — used when previewing a
	 * preset chip *before* selecting it, so we don't mutate Frappe's <audio>
	 * elements. Honors the same 3-second cap as the global SoundManager.
	 */
	function previewUrl(url, volume) {
		if (!url) return;
		try {
			const a = new Audio(url);
			const v = typeof volume === "number" ? volume : 0.5;
			a.volume = Math.max(0, Math.min(1, v));
			const p = a.play();
			if (p && typeof p.catch === "function") p.catch(() => {});
			setTimeout(() => {
				try {
					a.pause();
					a.currentTime = 0;
				} catch (_e) {
					/* ignore */
				}
			}, 3000);
		} catch (_e) {
			/* file missing or autoplay blocked — silent fallback */
		}
	}

	// The last path segment, decoded for display. A malformed percent-escape
	// in a stored URL must not take the whole table down with a URIError.
	function fileNameOf(url) {
		const last = (url || "").split("/").pop() || "";
		try {
			return decodeURIComponent(last);
		} catch (_e) {
			return last;
		}
	}

	function escapeHtml(s) {
		if (window.frappe && frappe.utils && frappe.utils.escape_html) {
			return frappe.utils.escape_html(String(s == null ? "" : s));
		}
		return String(s == null ? "" : s).replace(
			/[&<>"']/g,
			(c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
		);
	}

	function injectUserMenuItem() {
		if (document.querySelector(".sound-settings-link")) return true;

		// Try several selectors — Frappe's user dropdown class varies slightly across versions.
		const candidates = [
			".dropdown-navbar-user .dropdown-menu",
			".navbar-user .dropdown-menu",
			".dropdown-menu[aria-labelledby='navbar-user']",
			".navbar .dropdown-menu-right",
		];
		let $menu = null;
		for (const sel of candidates) {
			const found = $(sel);
			if (found.length) {
				$menu = found.last();
				break;
			}
		}
		if (!$menu || !$menu.length) return false;

		const $item = $(
			`<li><a class="dropdown-item sound-settings-link" href="#">${__(
				"Sound Settings"
			)}</a></li>`
		);
		$item.find("a").on("click", (e) => {
			e.preventDefault();
			openSoundStudio();
		});
		$menu.append($item);
		return true;
	}

	async function openSoundStudio() {
		if (!window.frappe || !frappe.ui || !frappe.ui.Dialog) {
			console.warn("Sound Studio requires Frappe Desk.");
			return;
		}

		let res;
		try {
			res = await frappe.call({ method: "nexus_theme.api.get_user_sounds" });
		} catch (_err) {
			frappe.show_alert({ message: __("Could not load sound settings"), indicator: "red" });
			return;
		}
		const state = (res && res.message) || { enabled: 1, mapping: {} };

		const dialog = new frappe.ui.Dialog({
			title: __("Sound Studio"),
			size: "large",
			fields: [
				{
					fieldtype: "Check",
					fieldname: "enabled",
					label: __("Enable sounds"),
					default: state.enabled ? 1 : 0,
				},
				{ fieldtype: "HTML", fieldname: "table" },
			],
			primary_action_label: __("Done"),
			primary_action: () => dialog.hide(),
		});

		dialog.fields_dict.enabled.df.onchange = async () => {
			const enabled = dialog.get_value("enabled") ? 1 : 0;
			try {
				await frappe.call({
					method: "nexus_theme.api.toggle_user_sounds",
					args: { enabled },
				});
			} catch (_err) {
				// Refused (site-wide off) or failed: put the checkbox back so it
				// never shows a state the server did not accept.
				dialog.set_value("enabled", enabled ? 0 : 1);
				frappe.show_alert({
					message: __("Could not change sound setting"),
					indicator: "red",
				});
				return;
			}
			if (window.SoundManager) SoundManager.setEnabled(!!enabled);
		};

		const $table = dialog.fields_dict.table.$wrapper;
		// Render swaps inner HTML; handlers are delegated to $table so they
		// survive the swap. Bind once here — re-binding on every render would
		// stack duplicate listeners and fire each save N times, racing the
		// optimistic-lock check on User Sound Preference.
		const render = () => {
			$table.html(renderTable(state));
		};
		bindRowEvents($table, dialog, state, render);
		render();

		// Custom action: reset all sounds
		const injectResetAll = () => {
			const $footer = dialog.$wrapper.find(".modal-footer").first();
			if (!$footer.length || $footer.find(".btn-reset-sounds").length) return;
			const $btn = $(
				`<button type="button" class="btn btn-default btn-sm btn-reset-sounds">${__(
					"Reset All to Default"
				)}</button>`
			);
			$btn.on("click", async () => {
				const ok = await new Promise((resolve) => {
					frappe.confirm(
						__("Remove all custom sounds? Frappe's defaults will play again."),
						() => resolve(true),
						() => resolve(false)
					);
				});
				if (!ok) return;
				try {
					await frappe.call({ method: "nexus_theme.api.clear_all_user_sounds" });
				} catch (_err) {
					frappe.show_alert({ message: __("Could not reset sounds"), indicator: "red" });
					return;
				}
				state.mapping = {};
				if (window.SoundManager) SoundManager.applyMapping({});
				render();
				frappe.show_alert({ message: __("All sounds reset"), indicator: "green" });
			});
			const $slot = $footer.find(".custom-actions").first();
			if ($slot.length) $slot.append($btn);
			else $footer.prepend($btn);
		};
		injectResetAll();
		dialog.$wrapper.on("shown.bs.modal", injectResetAll);

		dialog.show();
	}

	function renderTable(state) {
		return `
      <div class="sound-studio">
        <div class="sound-studio-hint">
          ${__("Upload your own audio for any event. Sounds are always cut at 3 seconds.")}
        </div>
        <div class="sound-studio-rows">
          ${EVENTS.map((e) => renderRow(e, state.mapping[e.key])).join("")}
        </div>
      </div>`;
	}

	function renderRow(event, mapped) {
		const hasCustom = !!(mapped && mapped.url);
		const volume = mapped && typeof mapped.volume === "number" ? mapped.volume : 0.5;
		const savedUrl = (mapped && mapped.url) || "";
		const selectedIdx = selectedPresetIndex(event.key, savedUrl);
		const isCustomUpload = hasCustom && selectedIdx === -1;
		const fileLabel = !hasCustom
			? __("Using default")
			: selectedIdx >= 0
			? __("Preset:") + " " + (PRESETS[event.key][selectedIdx].label || "")
			: fileNameOf(savedUrl);

		const presets = PRESETS[event.key] || [];
		const presetChips = presets
			.map((p, i) => {
				const sel = i === selectedIdx ? " is-selected" : "";
				return `
          <button type="button" class="preset-chip${sel}" data-preset-idx="${i}"
                  title="${escapeHtml(p.label)}">
            <span class="preset-play" data-action="preset-preview"
                  data-preset-idx="${i}" aria-label="${escapeHtml(__("Preview"))}">▶</span>
            <span class="preset-name">${escapeHtml(p.label)}</span>
          </button>`;
			})
			.join("");

		return `
      <div class="sound-row" data-event="${escapeHtml(event.key)}">
        <div class="sound-row-label">
          <div class="sound-row-title">${escapeHtml(__(event.label))}</div>
          <div class="sound-row-file">${escapeHtml(fileLabel)}</div>
        </div>
        <div class="sound-row-volume">
          <input type="range" min="0" max="100" value="${Math.round(volume * 100)}"
                 data-action="volume" aria-label="${escapeHtml(__("Volume"))}">
        </div>
        <div class="sound-row-actions">
          <button type="button" class="btn btn-xs btn-default" data-action="preview">${__(
				"Preview"
			)}</button>
          <button type="button" class="btn btn-xs btn-default" data-action="upload">${__(
				"Upload"
			)}</button>
          <button type="button" class="btn btn-xs btn-default" data-action="frappe-default"
                  title="${escapeHtml(__("Use Default Frappe Sound"))}">${__("Default")}</button>
          <button type="button" class="btn btn-xs btn-default" data-action="clear"
                  ${hasCustom ? "" : "disabled"}>${__("Clear")}</button>
        </div>
        <div class="sound-row-presets">
          <span class="presets-label">${escapeHtml(__("Defaults:"))}</span>
          ${presetChips}
          ${
				isCustomUpload
					? `<span class="preset-custom-tag">${escapeHtml(__("Custom uploaded"))}</span>`
					: ""
			}
        </div>
      </div>`;
	}

	function bindRowEvents($root, dialog, state, rerender) {
		$root.on("click", "[data-action='preview']", function () {
			const key = $(this).closest(".sound-row").data("event");
			// Previews route through the Frappe-internal key so aliased events
			// (Save → click) actually produce audible output.
			const playKey = PREVIEW_ALIAS[key] || key;
			if (window.frappe && frappe.utils && frappe.utils.play_sound) {
				frappe.utils.play_sound(playKey);
			}
		});

		$root.on("click", "[data-action='upload']", function () {
			const key = $(this).closest(".sound-row").data("event");
			openUploader(key, state, rerender);
		});

		// "Use Default Frappe Sound" — drop the custom mapping so Frappe's
		// bundled audio plays. Same backend semantics as Clear, but explicit.
		$root.on("click", "[data-action='frappe-default']", async function () {
			const key = $(this).closest(".sound-row").data("event");
			try {
				await frappe.call({
					method: "nexus_theme.api.clear_user_sound",
					args: { event_key: key },
				});
			} catch (_err) {
				frappe.show_alert({ message: __("Could not reset sound"), indicator: "red" });
				return;
			}
			delete state.mapping[key];
			if (window.SoundManager) SoundManager.resetMappingFor(key);
			rerender();
			// Preview the now-active Frappe default so the change is audible.
			const playKey = PREVIEW_ALIAS[key] || key;
			if (window.frappe && frappe.utils && frappe.utils.play_sound) {
				frappe.utils.play_sound(playKey);
			}
			frappe.show_alert({
				message: __("Using Frappe default sound"),
				indicator: "green",
			});
		});

		$root.on("click", "[data-action='clear']", async function () {
			const key = $(this).closest(".sound-row").data("event");
			try {
				await frappe.call({
					method: "nexus_theme.api.clear_user_sound",
					args: { event_key: key },
				});
			} catch (_err) {
				frappe.show_alert({ message: __("Could not clear sound"), indicator: "red" });
				return;
			}
			delete state.mapping[key];
			if (window.SoundManager) SoundManager.resetMappingFor(key);
			rerender();
			frappe.show_alert({ message: __("Cleared"), indicator: "green" });
		});

		// Preset preview — play a one-shot preview of the preset URL without
		// committing it to the user's saved mapping. Stop propagation so the
		// chip's parent click (which selects the preset) doesn't also fire.
		$root.on("click", "[data-action='preset-preview']", function (e) {
			e.stopPropagation();
			const $chip = $(this).closest(".preset-chip");
			const $row = $chip.closest(".sound-row");
			const key = $row.data("event");
			const idx = parseInt($chip.data("preset-idx"), 10);
			const preset = (PRESETS[key] || [])[idx];
			if (!preset) return;
			const mapped = state.mapping[key];
			const vol = mapped && typeof mapped.volume === "number" ? mapped.volume : 0.5;
			previewUrl(preset.url, vol);
		});

		// Preset select — persist the chosen preset URL via the existing
		// set_user_sound API and update SoundManager's runtime mapping so
		// the new sound takes effect immediately.
		$root.on("click", ".preset-chip", async function () {
			const $chip = $(this);
			const $row = $chip.closest(".sound-row");
			const key = $row.data("event");
			const idx = parseInt($chip.data("preset-idx"), 10);
			const preset = (PRESETS[key] || [])[idx];
			if (!preset) return;
			const existing = state.mapping[key];
			const volume = existing && typeof existing.volume === "number" ? existing.volume : 0.5;
			try {
				await frappe.call({
					method: "nexus_theme.api.set_user_sound",
					args: { event_key: key, file_url: preset.url, volume },
				});
			} catch (_e) {
				frappe.show_alert({ message: __("Could not save preset"), indicator: "red" });
				return;
			}
			state.mapping[key] = { url: preset.url, volume };
			if (window.SoundManager) SoundManager.applyMapping(state.mapping);
			rerender();
			// Audible confirmation.
			previewUrl(preset.url, volume);
		});

		$root.on("input", "[data-action='volume']", function () {
			const key = $(this).closest(".sound-row").data("event");
			const vol = parseInt(this.value, 10) / 100;
			if (window.SoundManager) {
				SoundManager.mapping[key] = SoundManager.mapping[key] || { url: null };
				SoundManager.mapping[key].volume = vol;
			}
		});

		$root.on("change", "[data-action='volume']", async function () {
			const key = $(this).closest(".sound-row").data("event");
			const vol = parseInt(this.value, 10) / 100;
			const mapped = state.mapping[key];
			if (!mapped || !mapped.url) return; // only persist if a custom file exists
			try {
				await frappe.call({
					method: "nexus_theme.api.set_user_sound",
					args: { event_key: key, file_url: mapped.url, volume: vol },
				});
			} catch (_err) {
				frappe.show_alert({ message: __("Could not save volume"), indicator: "red" });
				return;
			}
			state.mapping[key].volume = vol;
		});
	}

	function openUploader(eventKey, state, rerender) {
		if (!frappe.ui || !frappe.ui.FileUploader) {
			frappe.show_alert({
				message: __("Uploader not available"),
				indicator: "red",
			});
			return;
		}
		new frappe.ui.FileUploader({
			doctype: "User Sound Preference",
			docname: frappe.session.user,
			folder: "Home/Attachments",
			allow_multiple: false,
			restrictions: { allowed_file_types: ["audio/*"] },
			on_success: async (file_doc) => {
				const existing = state.mapping[eventKey];
				const volume =
					existing && typeof existing.volume === "number" ? existing.volume : 0.5;
				try {
					await frappe.call({
						method: "nexus_theme.api.set_user_sound",
						args: {
							event_key: eventKey,
							file_url: file_doc.file_url,
							volume,
						},
					});
				} catch (_err) {
					frappe.show_alert({
						message: __("Uploaded, but it could not be saved as your sound"),
						indicator: "red",
					});
					return;
				}
				state.mapping[eventKey] = { url: file_doc.file_url, volume };
				if (window.SoundManager) {
					SoundManager.applyMapping(state.mapping);
				}
				rerender();
				frappe.show_alert({
					message: __("Sound uploaded"),
					indicator: "green",
				});
			},
		});
	}

	function boot() {
		// Same story as the theme switcher: the v13–v15 user dropdown these
		// selectors target does not exist in v16, so this polled for ten
		// seconds on every page load and found nothing. Sound Settings is
		// reached through its Navbar Item there.
		if (!document.querySelector(".dropdown-navbar-user, .navbar-user")) return;
		let attempts = 0;
		const tryInject = () => {
			if (injectUserMenuItem()) return;
			if (attempts++ < 40) setTimeout(tryInject, 250);
		};
		tryInject();
	}

	if (window.frappe && typeof frappe.ready === "function") {
		frappe.ready(boot);
	} else if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", boot);
	} else {
		boot();
	}

	window.openSoundStudio = openSoundStudio;
})();
