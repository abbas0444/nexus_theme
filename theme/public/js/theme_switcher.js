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

    const container =
      document.querySelector(".navbar .navbar-collapse .navbar-nav.ms-auto") ||
      document.querySelector(".navbar .navbar-collapse .navbar-nav:last-child") ||
      document.querySelector("header .navbar-nav");

    if (!container) return false;

    const li = document.createElement("li");
    li.className = "nav-item theme-switcher-btn";
    li.innerHTML = `
      <a class="nav-link" href="#" title="Customize Theme" aria-label="Customize Theme" role="button">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10"></circle>
          <path d="M12 2a10 10 0 0 0 0 20 5 5 0 0 0 0-10 5 5 0 0 1 0-10z"></path>
        </svg>
      </a>`;
    li.querySelector("a").addEventListener("click", (e) => {
      e.preventDefault();
      openSwitcher();
    });
    container.insertBefore(li, container.firstChild);
    return true;
  }

  async function openSwitcher() {
    if (!window.frappe || !frappe.call || !frappe.ui || !frappe.ui.Dialog) {
      console.warn("Theme Switcher requires Frappe Desk.");
      return;
    }

    const res = await frappe.call({ method: "theme.api.get_available_themes" });
    const data = (res && res.message) || {};
    const defaults = data.defaults || [];
    const owned = data.owned || [];
    const publicThemes = data.public || [];

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
      // Tag the wrapper so CSS in theme_switcher.css can opt-out of the
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
        await ThemeManager.setActive(selectedTheme.name, overrides);
        frappe.show_alert({ message: __("Theme applied"), indicator: "green" });
        dialog.hide();
      },
      secondary_action_label: __("Save as Custom…"),
      secondary_action: () => {
        if (editor) editor.openSaveCustom();
      },
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
          __("Switch back to Frappe's default UI? This removes your theme preference."),
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

    injectResetButton();
    dialog.$wrapper.on("shown.bs.modal", injectResetButton);

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
    bindGalleryEvents($gallery, (name) => {
      const next = themesByName.get(name);
      if (!next) return;
      selectedTheme = next;
      // Switching themes wipes editor overrides — the previous overrides
      // were tuned for the previous theme and would bleed into this one.
      if (editor) editor.reset();
      renderPreview();
      if (editor) editor.refresh();
    });

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
  // in theme_switcher.css use them, which lets `:hover` work.
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

  function bindGalleryEvents($gallery, onSelect) {
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
          method: "theme.api.delete_custom_theme",
          args: { theme_name: name },
        });
        card.remove();
        frappe.show_alert({ message: __("Theme deleted"), indicator: "green" });
      } catch (_err) {
        frappe.show_alert({ message: __("Failed to delete theme"), indicator: "red" });
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
})();
