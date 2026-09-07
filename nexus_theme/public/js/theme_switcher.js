(function () {
  "use strict";

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

  function cssEscape(s) {
    if (window.CSS && typeof CSS.escape === "function") return CSS.escape(s);
    return String(s == null ? "" : s).replace(/["\\]/g, "\\$&");
  }

  function injectNavbarButton() {
    if (document.querySelector(".theme-switcher-btn")) return true;

    const candidates = [
      ".navbar .navbar-collapse .navbar-nav.ms-auto",
      ".navbar .navbar-collapse .navbar-nav:last-child",
      ".navbar .navbar-nav",
      "header .navbar-nav",
      ".navbar-nav",
      "nav.navbar-nav",
      ".navbar-collapse .navbar-nav",
    ];

    let container = null;
    for (const selector of candidates) {
      container = document.querySelector(selector);
      if (container) break;
    }

    if (!container) return false;

    const listItem = document.createElement("li");
    listItem.className = "nav-item theme-switcher-btn";
    listItem.innerHTML = `
      <a class="nav-link" href="#" title="Customize Theme" aria-label="Customize Theme" role="button">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10"></circle>
          <path d="M12 2a10 10 0 0 0 0 20 5 5 0 0 0 0-10 5 5 0 0 1 0-10z"></path>
        </svg>
      </a>`;
    listItem.querySelector("a").addEventListener("click", (e) => {
      e.preventDefault();
      openSwitcher();
    });

    const firstChild = container.firstElementChild;
    if (firstChild) {
      container.insertBefore(listItem, firstChild);
    } else {
      container.appendChild(listItem);
    }
    return true;
  }

  async function openSwitcher() {
    if (!window.frappe || !frappe.call || !frappe.ui || !frappe.ui.Dialog) {
      console.warn("Theme Switcher requires Frappe Desk.");
      return;
    }

    let res;
    try {
      res = await frappe.call({ method: "nexus_theme.api.get_available_themes" });
    } catch (_err) {
      frappe.show_alert({ message: __("Could not load themes"), indicator: "red" });
      return;
    }
    const data = (res && res.message) || {};
    const defaults = data.defaults || [];
    const owned = data.owned || [];
    const publicThemes = data.public || [];
    // Site governance. Absent (older server) means "everything allowed", so
    // the dialog behaves exactly as it did before Theme Settings existed.
    const gov = data.settings || { allow_custom_themes: 1, allow_public_sharing: 1 };

    // Build a flat lookup so card clicks resolve to full theme dicts
    // without another server round-trip.
    const allThemes = [...defaults, ...owned, ...publicThemes];
    const themesByName = new Map(allThemes.map((t) => [t.name, t]));

    let editor = null;
    // The dialog tracks its own "selected" state — a candidate theme +
    // candidate overrides. The live page is NOT touched until the user
    // clicks Apply. selectedTheme falls back to the active theme if any,
    // otherwise the first default so the preview always has something
    // to render.
    const initialActive = (window.ThemeManager && ThemeManager.active) || null;
    let selectedTheme =
      (initialActive && themesByName.get(initialActive.name)) ||
      initialActive ||
      defaults[0] ||
      null;

    const dialog = new frappe.ui.Dialog({
      title: __("Theme Studio"),
      size: "large",
      // Tag the wrapper so CSS in theme_switcher.bundle.css can opt-out of the
      // currently-active theme's variables — we want the studio itself to
      // stay legible no matter what theme the user is previewing.
      custom_cls: "theme-studio-isolated",
      fields: [
        { fieldtype: "HTML", fieldname: "preview" },
        { fieldtype: "HTML", fieldname: "gallery" },
        { fieldtype: "Section Break", label: __("Customize") },
        { fieldtype: "HTML", fieldname: "editor" },
      ],
      primary_action_label: __("Apply"),
      primary_action: async () => {
        if (!selectedTheme) {
          frappe.show_alert({ message: __("Pick a theme first"), indicator: "orange" });
          return;
        }
        const overrides = editor ? editor.getOverrides() : {};
        try {
          await ThemeManager.setActive(selectedTheme.name, overrides);
        } catch (err) {
          // The server's own reason is already on screen via frappe.call;
          // this keeps the dialog open instead of an unhandled rejection.
          frappe.show_alert({
            message: __("Could not apply theme: {0}", [(err && err.message) || ""]),
            indicator: "red",
          });
          return;
        }
        frappe.show_alert({ message: __("Theme applied"), indicator: "green" });
        dialog.hide();
      },
      secondary_action_label: gov.allow_custom_themes
        ? __("Save as Custom…")
        : undefined,
      secondary_action: gov.allow_custom_themes
        ? () => {
            if (editor) editor.openSaveCustom();
          }
        : undefined,
    });

    // Safety net: regardless of `custom_cls` support, force the class onto
    // every level of the modal chrome so our scoped CSS matches no matter
    // which subtree Frappe renders content into.
    const ISO = "theme-studio-isolated";
    dialog.$wrapper.addClass(ISO);
    dialog.$wrapper.find(".modal-dialog").addClass(ISO);
    dialog.$wrapper.find(".modal-content").addClass(ISO);
    dialog.$wrapper.on("shown.bs.modal", () => {
      dialog.$wrapper.find(".modal-dialog, .modal-content").addClass(ISO);
    });

    // No revert-on-close needed: the dialog never mutates the live page.
    // Anything the user did inside is discarded automatically because
    // there's nothing to discard from <html>.

    const handleReset = async () => {
      const confirmed = await new Promise((resolve) => {
        frappe.confirm(
          __("Switch back to Frappe's own look? Your theme choice will be cleared."),
          () => resolve(true),
          () => resolve(false)
        );
      });
      if (!confirmed) return;
      try {
        await ThemeManager.resetToFrappeDefault();
        frappe.show_alert({
          message: __("Reverted to Frappe default"),
          indicator: "green",
        });
        dialog.hide();
      } catch (_err) {
        frappe.show_alert({
          message: __("Could not reset theme"),
          indicator: "red",
        });
      }
    };

    const injectResetButton = () => {
      const $footer = dialog.$wrapper.find(".modal-footer").first();
      if (!$footer.length) return false;
      if ($footer.find(".btn-reset-theme").length) return true;
      const $btn = $(
        `<button type="button" class="btn btn-default btn-sm btn-reset-theme">${__(
          "Reset to Default"
        )}</button>`
      );
      $btn.on("click", handleReset);
      const $slot = $footer.find(".custom-actions").first();
      if ($slot.length) {
        $slot.append($btn);
      } else {
        $btn.css("margin-right", "auto");
        $footer.prepend($btn);
      }
      return true;
    };

    // ---- Automatic light/dark pairing ----
    const handleAutoPair = async () => {
      const allThemes = [...defaults, ...owned, ...publicThemes];
      const darkThemes = allThemes.filter((t) => t.is_dark);
      const lightThemes = allThemes.filter((t) => !t.is_dark);
      if (!darkThemes.length || !lightThemes.length) {
        frappe.show_alert({
          message: __("Automatic mode needs both a light and a dark theme available"),
          indicator: "orange",
        });
        return;
      }
      const current = (window.ThemeManager && ThemeManager.mode) || "Single";
      const pair = (window.ThemeManager && ThemeManager.pair) || {};

      const d = new frappe.ui.Dialog({
        title: __("Automatic Light / Dark"),
        fields: [
          {
            fieldtype: "HTML",
            fieldname: "intro",
            options: `<p class="text-muted">${__(
              "Follow the operating system: your light theme during the day, your dark theme at night."
            )}</p>`,
          },
          {
            fieldtype: "Select",
            fieldname: "mode",
            label: __("Mode"),
            options: "Single\nAutomatic",
            default: current,
          },
          {
            fieldtype: "Select",
            fieldname: "light_theme",
            label: __("Light Theme"),
            depends_on: "eval:doc.mode=='Automatic'",
            options: lightThemes.map((t) => t.name).join("\n"),
            default: (pair.light && !pair.light.is_dark && pair.light.name) || undefined,
          },
          {
            fieldtype: "Select",
            fieldname: "dark_theme",
            label: __("Dark Theme"),
            depends_on: "eval:doc.mode=='Automatic'",
            options: darkThemes.map((t) => t.name).join("\n"),
            default: (pair.dark && pair.dark.name) || undefined,
          },
        ],
        primary_action_label: __("Save"),
        primary_action: async (v) => {
          try {
            if (v.mode === "Automatic") {
              if (!v.light_theme || !v.dark_theme) {
                frappe.show_alert({
                  message: __("Pick both a light and a dark theme"),
                  indicator: "orange",
                });
                return;
              }
              // The light half is the stored active theme, so set it first.
              await ThemeManager.setActive(v.light_theme, {});
              await ThemeManager.setThemeMode("Automatic", v.dark_theme);
            } else {
              await ThemeManager.setThemeMode("Single", null);
            }
            frappe.show_alert({ message: __("Saved"), indicator: "green" });
            d.hide();
            dialog.hide();
          } catch (err) {
            frappe.show_alert({
              message: __("Could not save: {0}", [(err && err.message) || ""]),
              indicator: "red",
            });
          }
        },
      });
      d.show();
    };

    // ---- Export / import ----
    const handleExport = async () => {
      if (!selectedTheme) {
        frappe.show_alert({ message: __("Pick a theme first"), indicator: "orange" });
        return;
      }
      try {
        const r = await frappe.call({
          method: "nexus_theme.api.export_theme",
          args: { theme_name: selectedTheme.name },
        });
        if (!r || !r.message) return;
        const blob = new Blob([JSON.stringify(r.message, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${selectedTheme.theme_key || "theme"}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        // Revoking immediately can cancel the download in some browsers.
        setTimeout(() => URL.revokeObjectURL(url), 2000);
      } catch (_err) {
        frappe.show_alert({ message: __("Could not export theme"), indicator: "red" });
      }
    };

    const handleImport = () => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = "application/json,.json";
      input.addEventListener("change", async () => {
        const file = input.files && input.files[0];
        if (!file) return;
        try {
          const text = await file.text();
          const r = await frappe.call({
            method: "nexus_theme.api.import_theme",
            args: { payload: text },
          });
          if (r && r.message && r.message.name) {
            frappe.show_alert({ message: __("Theme imported"), indicator: "green" });
            dialog.hide();
            openSwitcher();
          }
        } catch (err) {
          frappe.show_alert({
            message: __("Could not import: {0}", [(err && err.message) || ""]),
            indicator: "red",
          });
        }
      });
      input.click();
    };

    // ---- Login page preview ----
    // One dialog, reused: frappe.ui.Dialog leaves its markup in the DOM after
    // hide(), so building a new one per click would stack copies of the
    // preview behind the studio.
    let loginInfo = null;
    let loginPreviewDialog = null;
    const handleViewLogin = async () => {
      if (!loginInfo) {
        try {
          const r = await frappe.call({ method: "nexus_theme.api.get_login_preview" });
          loginInfo = (r && r.message) || {};
        } catch (_err) {
          loginInfo = {};
        }
      }
      const overrides = editor ? editor.getOverrides() : {};
      const note = loginInfo.enabled
        ? __("This is your sign-in screen with the theme selected above.")
        : __(
            "This is how your sign-in screen would look. It is not switched on yet: a System Manager turns it on in Theme Settings."
          );

      if (!loginPreviewDialog) {
        loginPreviewDialog = new frappe.ui.Dialog({
          title: __("Login Page"),
          size: "large",
          custom_cls: "theme-studio-isolated",
          fields: [{ fieldtype: "HTML", fieldname: "login_preview" }],
          primary_action_label: __("Close"),
          primary_action: () => loginPreviewDialog.hide(),
        });
        loginPreviewDialog.$wrapper.addClass("theme-studio-isolated");
        loginPreviewDialog.$wrapper
          .find(".modal-dialog, .modal-content")
          .addClass("theme-studio-isolated");
      }

      // Rebuilt on every open so it always shows the theme selected right now.
      loginPreviewDialog.fields_dict.login_preview.$wrapper.html(
        `<div class="nxlp-wrap">
          ${buildLoginPreviewHTML(selectedTheme, overrides, loginInfo)}
          <p class="nxlp-note">${escapeHtml(note)}</p>
        </div>`
      );
      loginPreviewDialog.show();
    };

    const injectFooterButtons = () => {
      const $footer = dialog.$wrapper.find(".modal-footer").first();
      if (!$footer.length) return;
      const $slot = $footer.find(".custom-actions").first();
      const place = ($btn) => {
        if ($slot.length) $slot.append($btn);
        else $footer.prepend($btn);
      };

      const add = (cls, label, handler) => {
        if ($footer.find("." + cls).length) return;
        const $btn = $(
          `<button type="button" class="btn btn-default btn-sm ${cls}">${label}</button>`
        );
        $btn.on("click", handler);
        place($btn);
      };

      add("btn-view-login", __("View Login"), handleViewLogin);
      add("btn-auto-pair", __("Auto Light/Dark"), handleAutoPair);
      add("btn-export-theme", __("Export"), handleExport);
      if (gov.allow_custom_themes) {
        add("btn-import-theme", __("Import"), handleImport);
      }
    };

    injectResetButton();
    injectFooterButtons();
    dialog.$wrapper.on("shown.bs.modal", () => {
      injectResetButton();
      injectFooterButtons();
    });

    // ---- Preview pane ----
    const $preview = dialog.fields_dict.preview.$wrapper;
    const renderPreview = () => {
      const overrides = editor ? editor.getOverrides() : {};
      $preview.html(buildPreviewHTML(selectedTheme, overrides));
    };

    // ---- Gallery ----
    const $gallery = dialog.fields_dict.gallery.$wrapper;
    const selectedName = selectedTheme ? selectedTheme.name : null;
    $gallery.html(renderGallery({ defaults, owned, publicThemes }, selectedName));
    const selectTheme = (name) => {
      const next = themesByName.get(name);
      if (!next) return;
      selectedTheme = next;
      // Switching themes wipes editor overrides — the previous overrides
      // were tuned for the previous theme and would bleed into this one.
      if (editor) editor.reset();
      renderPreview();
      if (editor) editor.refresh();
    };

    // A deleted theme must not linger anywhere the dialog could still act
    // on it: the lookup, the section list Auto Light/Dark reads, the
    // selection Apply would send, or the live page if it was showing.
    const onDeleted = (name) => {
      themesByName.delete(name);
      const i = owned.findIndex((t) => t.name === name);
      if (i >= 0) owned.splice(i, 1);

      if (selectedTheme && selectedTheme.name === name) {
        selectedTheme = defaults[0] || owned[0] || publicThemes[0] || null;
        if (editor) editor.reset();
        renderPreview();
        if (editor) editor.refresh();
        $gallery.find(".theme-card").removeClass("is-selected");
        if (selectedTheme) {
          $gallery
            .find(`.theme-card[data-name="${cssEscape(selectedTheme.name)}"]`)
            .addClass("is-selected");
        }
      }

      const live = window.ThemeManager && ThemeManager.active;
      if (live && live.name === name && typeof ThemeManager.loadFromServer === "function") {
        // The server has already released it; pull the fallback down now
        // rather than leaving a theme that no longer exists on the page.
        ThemeManager.loadFromServer();
      }
    };

    bindGalleryEvents($gallery, selectTheme, onDeleted);

    // ---- ThemeManager.onChange (external sync) ----
    // If another tab or Frappe's native toggle changes the live theme
    // while the dialog is open, just update the gallery highlight so
    // the dialog's selection state never lies. We do NOT auto-replace
    // the preview — the user is mid-edit.
    let unsubscribe = null;
    if (window.ThemeManager && typeof ThemeManager.onChange === "function") {
      unsubscribe = ThemeManager.onChange((active) => {
        const liveName = (active && active.name) || null;
        $gallery.find(".theme-card").removeClass("is-selected");
        if (liveName) {
          $gallery
            .find(`.theme-card[data-name="${cssEscape(liveName)}"]`)
            .addClass("is-selected");
        }
      });
    }
    dialog.$wrapper.on("hidden.bs.modal", () => {
      if (unsubscribe) unsubscribe();
    });

    // ---- Editor ----
    const $editor = dialog.fields_dict.editor.$wrapper;
    if (window.openThemeEditor) {
      editor = window.openThemeEditor($editor, dialog, {
        getSelectedTheme: () => selectedTheme,
        onPreview: () => renderPreview(),
        allowPublicSharing: !!gov.allow_public_sharing,
      });
    }

    // First paint of the preview now that editor is ready
    renderPreview();

    dialog.show();
  }

  // ---- Preview mockup ----
  // Renders a mini "app" inside the dialog so the user sees how a theme
  // will feel — navbar + sidebar + form + table + button — without ever
  // touching the live page. Theme colors flow through `--mock-*` CSS
  // custom properties on the wrapper, then `.theme-preview-mockup` rules
  // in theme_switcher.bundle.css use them, which lets `:hover` work.
  function buildPreviewHTML(theme, overrides) {
    const t = Object.assign({}, theme || {}, overrides || {});
    const v = (key, fallback) => {
      const x = t[key];
      return x == null || x === "" ? fallback : x;
    };
    const radius = v("border_radius", "8px");
    const fontFamily = v("font_family", '"Inter", system-ui, sans-serif');

    // Build the wrapper's inline style from theme tokens — escapeHtml on
    // every value so a malformed theme can't inject CSS. We use plain
    // `style="..."` here because CSS custom properties are not reachable
    // any other way from this layer.
    const style = [
      `--mock-bg-primary:${escapeHtml(v("bg_primary", "#ffffff"))}`,
      `--mock-bg-surface:${escapeHtml(v("bg_surface", "#f7f8fa"))}`,
      `--mock-bg-input:${escapeHtml(v("bg_input", "#ffffff"))}`,
      `--mock-text-primary:${escapeHtml(v("text_primary", "#1f2937"))}`,
      `--mock-text-muted:${escapeHtml(v("text_muted", "#6b7280"))}`,
      `--mock-accent:${escapeHtml(v("accent", "#4f46e5"))}`,
      `--mock-accent-hover:${escapeHtml(v("accent_hover", "#4338ca"))}`,
      `--mock-button-bg:${escapeHtml(v("button_bg", "#4f46e5"))}`,
      `--mock-button-text:${escapeHtml(v("button_text", "#ffffff"))}`,
      `--mock-button-hover-bg:${escapeHtml(v("button_hover_bg", "#4338ca"))}`,
      `--mock-border:${escapeHtml(v("border", "#e5e7eb"))}`,
      `--mock-radius:${escapeHtml(radius)}`,
      `--mock-font-family:${escapeHtml(fontFamily)}`,
    ].join(";");

    const themeName = escapeHtml(v("theme_name", __("Preview")));

    return `
      <div class="theme-preview-section">
        <div class="theme-preview-heading">
          <span>${escapeHtml(__("Live Preview"))}</span>
          <span class="theme-preview-themename">${themeName}</span>
        </div>
        <div class="theme-preview-mockup" style="${style}">
          <div class="tpm-navbar">
            <div class="tpm-logo"></div>
            <div class="tpm-navlinks">
              <span class="tpm-navlink is-active">${escapeHtml(__("Home"))}</span>
              <span class="tpm-navlink">${escapeHtml(__("Reports"))}</span>
              <span class="tpm-navlink">${escapeHtml(__("Settings"))}</span>
            </div>
          </div>
          <div class="tpm-body">
            <div class="tpm-sidebar">
              <div class="tpm-sideitem is-active">${escapeHtml(__("Dashboard"))}</div>
              <div class="tpm-sideitem">${escapeHtml(__("Customers"))}</div>
              <div class="tpm-sideitem">${escapeHtml(__("Invoices"))}</div>
              <div class="tpm-sideitem">${escapeHtml(__("Items"))}</div>
            </div>
            <div class="tpm-content">
              <div class="tpm-row tpm-row-form">
                <input class="tpm-input" type="text" placeholder="${escapeHtml(
                  __("Search customers…")
                )}" />
                <button type="button" class="tpm-button">${escapeHtml(__("New"))}</button>
              </div>
              <table class="tpm-table">
                <thead>
                  <tr>
                    <th>${escapeHtml(__("Customer"))}</th>
                    <th>${escapeHtml(__("Status"))}</th>
                    <th>${escapeHtml(__("Amount"))}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr><td>Acme Corp</td><td><span class="tpm-pill">${escapeHtml(__("Paid"))}</span></td><td>$12,400</td></tr>
                  <tr><td>Globex</td><td><span class="tpm-pill tpm-pill-muted">${escapeHtml(__("Pending"))}</span></td><td>$3,200</td></tr>
                  <tr><td>Initech</td><td><span class="tpm-pill">${escapeHtml(__("Paid"))}</span></td><td>$7,890</td></tr>
                </tbody>
              </table>
              <div class="tpm-hint">${escapeHtml(
                __("Hover the rows and the button — colors react with the theme accent.")
              )}</div>
            </div>
          </div>
        </div>
      </div>`;
  }

  // ------------------------------------------------------------------
  // Login page preview
  // ------------------------------------------------------------------
  // The sign-in screen is the one part of the theme a signed-in user cannot
  // see without signing out. This draws it from the same theme tokens the
  // real page consumes, and from the same words, so what it shows is what
  // the visitor gets.
  // ------------------------------------------------------------------
  function buildLoginPreviewHTML(theme, overrides, info) {
    const t = Object.assign({}, theme || {}, overrides || {});
    const v = (key, fallback) => {
      const x = t[key];
      return x == null || x === "" ? fallback : x;
    };

    const style = [
      `--nxlp-bg:${escapeHtml(v("bg_primary", "#ffffff"))}`,
      `--nxlp-input:${escapeHtml(v("bg_input", "#ffffff"))}`,
      `--nxlp-text:${escapeHtml(v("text_primary", "#16181d"))}`,
      `--nxlp-muted:${escapeHtml(v("text_muted", "#6b7280"))}`,
      `--nxlp-accent:${escapeHtml(v("accent", "#7c3aed"))}`,
      `--nxlp-accent-hover:${escapeHtml(v("accent_hover", "#6d28d9"))}`,
      `--nxlp-btn-bg:${escapeHtml(v("button_bg", v("accent", "#7c3aed")))}`,
      `--nxlp-btn-text:${escapeHtml(v("button_text", "#ffffff"))}`,
      `--nxlp-btn-hover:${escapeHtml(v("button_hover_bg", v("accent_hover", "#6d28d9")))}`,
      `--nxlp-border:${escapeHtml(v("border", "#e3e6ea"))}`,
      `--nxlp-radius:${escapeHtml(v("border_radius", "10px"))}`,
      `--nxlp-font:${escapeHtml(v("font_family", '"Inter", system-ui, sans-serif'))}`,
    ].join(";");

    const tick = `<svg viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/><path d="m6.4 10.2 2.4 2.4 4.8-4.8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

    const logo = info.brand_logo
      ? `<img class="nxlp-logo" src="${escapeHtml(info.brand_logo)}" alt="">`
      : "";
    const points = (info.points || [])
      .map((point) => `<li>${tick}<span>${escapeHtml(point)}</span></li>`)
      .join("");
    const stat =
      info.stat || info.stat_note
        ? `<div class="nxlp-stat">${
            info.stat ? `<b>${escapeHtml(info.stat)}</b>` : ""
          }<span>${escapeHtml(info.stat_note || "")}</span></div>`
        : "";
    const footnote = info.footnote
      ? `<div class="nxlp-foot">${escapeHtml(info.footnote)}</div>`
      : "";

    return `
      <div class="nxlp" style="${style}">
        <div class="nxlp-form">
          <div class="nxlp-brand">${logo}<span>${escapeHtml(info.brand_name || "")}</span></div>
          <div class="nxlp-title">${escapeHtml(__("Sign In"))}</div>
          <div class="nxlp-sub">${escapeHtml(
            info.subtitle || __("Welcome back. Please sign in to continue.")
          )}</div>
          <div class="nxlp-label">${escapeHtml(__("Email"))}</div>
          <div class="nxlp-input">${escapeHtml(__("Enter your username or email"))}</div>
          <div class="nxlp-label">${escapeHtml(__("Password"))}</div>
          <div class="nxlp-input nxlp-input-dots">••••••••</div>
          <div class="nxlp-row">
            <span class="nxlp-remember"><span class="nxlp-box"></span>${escapeHtml(
              __("Remember me")
            )}</span>
            <span class="nxlp-link">${escapeHtml(__("Forgot Password?"))}</span>
          </div>
          <div class="nxlp-btn">${escapeHtml(__("Sign In"))}</div>
          ${footnote}
        </div>
        <div class="nxlp-panel">
          <div class="nxlp-headline">${escapeHtml(info.headline || "")}</div>
          <div class="nxlp-panel-sub">${escapeHtml(info.subheadline || "")}</div>
          ${points ? `<ul class="nxlp-points">${points}</ul>` : ""}
          ${stat}
        </div>
      </div>`;
  }

  function renderGallery({ defaults, owned, publicThemes }, selectedName) {
    const section = (title, list, kind) => {
      if (!list.length) return "";
      return `
        <div class="theme-section">
          <div class="theme-section-title">${escapeHtml(title)}</div>
          <div class="theme-grid">
            ${list.map((t) => cardHTML(t, selectedName, kind)).join("")}
          </div>
        </div>`;
    };
    return (
      section(__("Default Themes"), defaults, "default") +
      section(__("My Custom Themes"), owned, "owned") +
      section(__("Shared by Others"), publicThemes, "public")
    );
  }

  function cardHTML(t, selectedName, kind) {
    const selected = t.name === selectedName ? "is-selected" : "";
    const deleteBtn =
      kind === "owned"
        ? `<button type="button" data-action="delete" title="${__("Delete")}">${__("Delete")}</button>`
        : "";

    // Tiny app mockup: navbar stripe + sidebar stripe + content area
    // with a primary button and two text lines. Communicates how the
    // theme actually feels far better than three abstract dots.
    const bgPrimary = escapeHtml(t.bg_primary || "#ffffff");
    const bgSurface = escapeHtml(t.bg_surface || "#f7f8fa");
    const textPrimary = escapeHtml(t.text_primary || "#1f2937");
    const textMuted = escapeHtml(t.text_muted || "#6b7280");
    const accent = escapeHtml(t.accent || "#4f46e5");
    const buttonBg = escapeHtml(t.button_bg || "#4f46e5");
    const buttonText = escapeHtml(t.button_text || "#ffffff");
    const border = escapeHtml(t.border || "#e5e7eb");
    const radius = escapeHtml(t.border_radius || "8px");
    const fontFamily = escapeHtml(t.font_family || "inherit");

    // Inline styles use `!important` because the Theme Studio dialog has
    // `.theme-studio-isolated * { color: …!important }` to prevent the
    // active theme from bleeding into the studio chrome — but the preview
    // *needs* per-theme colors. Inline !important wins on specificity.
    return `
      <div class="theme-card ${selected}" data-name="${escapeHtml(t.name)}"
           data-key="${escapeHtml(t.theme_key)}" tabindex="0" role="button"
           aria-label="${escapeHtml(t.theme_name)}">
        <div class="theme-card-preview"
             style="background:${bgPrimary} !important;
                    border:1px solid ${border} !important;
                    border-radius:${radius} !important;
                    font-family:${fontFamily} !important;">
          <div class="tcp-navbar"
               style="background:${bgSurface} !important; border-bottom:1px solid ${border} !important;">
            <div class="tcp-dot" style="background:${accent} !important;"></div>
            <div class="tcp-bar" style="background:${textMuted} !important;"></div>
          </div>
          <div class="tcp-body">
            <div class="tcp-sidebar"
                 style="background:${bgSurface} !important; border-right:1px solid ${border} !important;">
              <div class="tcp-line" style="background:${textMuted} !important;"></div>
              <div class="tcp-line tcp-line-short" style="background:${textMuted} !important;"></div>
              <div class="tcp-line" style="background:${textMuted} !important;"></div>
            </div>
            <div class="tcp-content">
              <div class="tcp-heading" style="color:${textPrimary} !important;">Aa</div>
              <div class="tcp-line tcp-line-text"
                   style="background:${textPrimary} !important; opacity:0.55;"></div>
              <div class="tcp-line tcp-line-text tcp-line-short"
                   style="background:${textMuted} !important;"></div>
              <div class="tcp-button"
                   style="background:${buttonBg} !important;
                          color:${buttonText} !important;
                          border-radius:${radius} !important;">
                Action
              </div>
            </div>
          </div>
        </div>
        <div class="theme-card-name">${escapeHtml(t.theme_name)}</div>
        <div class="theme-card-actions">${deleteBtn}</div>
      </div>`;
  }

  function bindGalleryEvents($gallery, onSelect, onDelete) {
    $gallery.on("click", ".theme-card", function (e) {
      if ($(e.target).closest("[data-action]").length) return;
      selectCard($gallery, this, onSelect);
    });

    $gallery.on("keydown", ".theme-card", function (e) {
      if (e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault();
      selectCard($gallery, this, onSelect);
    });

    $gallery.on("click", "[data-action='delete']", async function (e) {
      e.stopPropagation();
      const card = $(this).closest(".theme-card");
      const name = card.data("name");
      const confirmed = await new Promise((resolve) => {
        frappe.confirm(
          __("Delete this custom theme?"),
          () => resolve(true),
          () => resolve(false)
        );
      });
      if (!confirmed) return;
      try {
        await frappe.call({
          method: "nexus_theme.api.delete_custom_theme",
          args: { theme_name: name },
        });
        card.remove();
        if (typeof onDelete === "function") onDelete(name);
        frappe.show_alert({ message: __("Theme deleted"), indicator: "green" });
      } catch (err) {
        // A refusal (site default, allow-list) arrives with the server's own
        // message via frappe.call; this covers a plain network failure.
        frappe.show_alert({
          message: __("Could not delete theme: {0}", [(err && err.message) || ""]),
          indicator: "red",
        });
      }
    });
  }

  function selectCard($gallery, el, onSelect) {
    $gallery.find(".theme-card").removeClass("is-selected");
    el.classList.add("is-selected");
    const name = el.dataset.name;
    // The dialog handles its own preview through `onSelect` — we never
    // mutate the live page here. Apply only takes effect when the user
    // clicks the Apply button.
    onSelect(name);
  }

  function boot() {
    // Frappe v16 replaced the top navbar with the left sidebar, so none of
    // the selectors below exist any more and this quietly does nothing —
    // Theme Studio is reached through the Navbar Item registered by
    // install.ensure_navbar_items() instead. Kept for v15 and earlier,
    // where the navbar icon is still the only entry point.
    if (!document.querySelector(".navbar-nav")) return;
    let attempts = 0;
    const tryInject = () => {
      if (injectNavbarButton()) return;
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

  // The Navbar Item action calls this, and the README documents it as a
  // public entry point. It was never actually assigned, so Theme Studio had
  // no reachable opener at all once the navbar icon stopped resolving.
  window.openThemeSwitcher = openSwitcher;
})();
