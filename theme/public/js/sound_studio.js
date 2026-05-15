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
  // Presets point at Frappe's bundled audio (`/assets/frappe/sounds/*.mp3`)
  // so they work out of the box. Per-event picks are chosen to fit the
  // action: positive/welcoming sounds for login & save, firmer ones for
  // delete & error, etc. To swap in your own audio later, drop MP3s into
  // `theme/public/sounds/` (served at `/assets/theme/sounds/<file>.mp3`)
  // and edit the URLs below.
  // Bundled with the app — see theme/public/sounds/. Served by Frappe at
  // /assets/theme/sounds/<name>.mp3. Self-contained, no dependency on
  // /assets/frappe/sounds remaining stable.
  const SND = (name) => `/assets/theme/sounds/${name}.mp3`;

  const PRESETS = {
    login: [
      { label: "Unlock", url: "/assets/theme/sounds/mixkit-computer-digital-lock-2859.wav" },
      { label: "Access", url: "/assets/theme/sounds/mixkit-gaming-lock-2848.wav"           },
      { label: "Entry",  url: "/assets/theme/sounds/mixkit-video-game-lock-2851.wav"       },
    ],
    logout: [
      { label: "Cancel", url: SND("cancel") },
      { label: "Click",  url: SND("click")  },
      { label: "Alert",  url: SND("alert")  },
    ],
    save: [
      { label: "Jump",  url:"/assets/theme/sounds/mixkit-arcade-game-jump-coin-216.wav"},
      { label: "retro", url:"/assets/theme/sounds/mixkit-retro-arcade-casino-notification-211.wav" },
      { label: "Email",  url: SND("email")  },
    ],
    submit: [
      { label: "Beep",    url: "/assets/theme/sounds/mixkit-positive-interface-beep-221.wav" },
      { label: "Cheer",   url: "/assets/theme/sounds/mixkit-quick-positive-video-game-notification-interface-265.wav" },
      { label: "Victory", url: "/assets/theme/sounds/mixkit-quick-win-video-game-notification-269.wav" },
    ],
    cancel: [
      { label: "Cancel", url: SND("cancel") },
      { label: "Click",  url: SND("click")  },
      { label: "Error",  url: SND("error")  },
    ],
    delete: [
      { label: "Erase", url: "/assets/theme/sounds/mixkit-software-interface-remove-2576.wav" },
      { label: "Undo",  url: "/assets/theme/sounds/mixkit-software-interface-back-2575.wav"  },
      { label: "Snap",  url: "/assets/theme/sounds/mixkit-on-or-off-light-switch-tap-2585.wav" },
    ],
    error: [
      { label: "Glitch", url: "/assets/theme/sounds/mixkit-sci-fi-error-alert-898.wav"        },
      { label: "Buzz",   url: "/assets/theme/sounds/mixkit-system-beep-buzzer-fail-2964.wav"  },
      { label: "Thud",   url: "/assets/theme/sounds/mixkit-negative-tone-interface-tap-2569.wav" },
    ],
    email: [
      { label: "Email",  url: SND("email")  },
      { label: "Alert",  url: SND("alert")  },
      { label: "Chime",  url: SND("chime")  },
    ],
    alert: [
      { label: "Chirp", url: "/assets/theme/sounds/mixkit-alert-quick-chime-766.wav"               },
      { label: "Sweep", url: "/assets/theme/sounds/mixkit-explainer-video-game-alert-sweep-236.wav" },
      { label: "Siren", url: "/assets/theme/sounds/mixkit-residential-burglar-siren-1657.wav"      },
    ],
    notification: [
      { label: "Pulse", url: "/assets/theme/sounds/mixkit-handgun-click-1660.mp3" },
      { label: "Beam",  url: "/assets/theme/sounds/mixkit-sci-fi-click-900.wav"  },
      { label: "Tap",   url: "/assets/theme/sounds/mixkit-select-click-1109.wav" },
    ],
    missing_fields: [
      { label: "Glitch", url: "/assets/theme/sounds/mixkit-sci-fi-error-alert-898.wav"        },
      { label: "Buzz",   url: "/assets/theme/sounds/mixkit-system-beep-buzzer-fail-2964.wav"  },
      { label: "Thud",   url: "/assets/theme/sounds/mixkit-negative-tone-interface-tap-2569.wav" },
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

  function escapeHtml(s) {
    if (window.frappe && frappe.utils && frappe.utils.escape_html) {
      return frappe.utils.escape_html(String(s == null ? "" : s));
    }
    return String(s == null ? "" : s).replace(
      /[&<>"']/g,
      (c) =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
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

    const res = await frappe.call({ method: "theme.api.get_user_sounds" });
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
      await frappe.call({
        method: "theme.api.toggle_user_sounds",
        args: { enabled },
      });
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
        await frappe.call({ method: "theme.api.clear_all_user_sounds" });
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
          ${__(
            "Upload your own audio for any event. Sounds are always cut at 3 seconds."
          )}
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
      : decodeURIComponent((savedUrl || "").split("/").pop() || "");

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
      await frappe.call({
        method: "theme.api.clear_user_sound",
        args: { event_key: key },
      });
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
      await frappe.call({
        method: "theme.api.clear_user_sound",
        args: { event_key: key },
      });
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
      const volume =
        existing && typeof existing.volume === "number" ? existing.volume : 0.5;
      try {
        await frappe.call({
          method: "theme.api.set_user_sound",
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
      await frappe.call({
        method: "theme.api.set_user_sound",
        args: { event_key: key, file_url: mapped.url, volume: vol },
      });
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
        const volume = existing && typeof existing.volume === "number" ? existing.volume : 0.5;
        await frappe.call({
          method: "theme.api.set_user_sound",
          args: {
            event_key: eventKey,
            file_url: file_doc.file_url,
            volume,
          },
        });
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
