(function () {
  "use strict";

  // ------------------------------------------------------------------
  // Field catalog
  // ------------------------------------------------------------------
  // Same field set as before, plus font_weight_base which was missing
  // (VAR_MAP in theme_manager.js already supports it). Each field is
  // tagged with `tier: "basic" | "advanced"` so we can render two views
  // of the same data without forking definitions.
  const FIELDS = [
    { key: "bg_primary",       label: "Background",        type: "color",  tier: "basic"    },
    { key: "bg_surface",       label: "Surface / Cards",   type: "color",  tier: "advanced" },
    { key: "bg_input",         label: "Input Background",  type: "color",  tier: "advanced" },
    { key: "text_primary",     label: "Text Color",        type: "color",  tier: "basic"    },
    { key: "text_muted",       label: "Muted Text",        type: "color",  tier: "advanced" },
    { key: "accent",           label: "Accent",            type: "color",  tier: "basic"    },
    { key: "accent_hover",     label: "Accent Hover",      type: "color",  tier: "advanced" },
    { key: "button_bg",        label: "Button Color",      type: "color",  tier: "advanced" },
    { key: "button_text",      label: "Button Text",       type: "color",  tier: "advanced" },
    { key: "button_hover_bg",  label: "Button Hover",      type: "color",  tier: "advanced" },
    { key: "border",           label: "Border",            type: "color",  tier: "advanced" },
    {
      key: "font_family", label: "Font Family", type: "select", tier: "basic",
      options: [
        '"Inter", system-ui, sans-serif',
        '"Roboto", sans-serif',
        '"JetBrains Mono", ui-monospace, monospace',
        '"Georgia", serif',
        '"Source Sans Pro", sans-serif',
        '"Segoe UI", system-ui, sans-serif',
      ],
    },
    {
      key: "font_size_base", label: "Font Size", type: "select", tier: "basic",
      options: ["12px", "13px", "14px", "15px", "16px", "18px"],
    },
    {
      key: "font_weight_base", label: "Font Weight", type: "select", tier: "advanced",
      options: ["300", "400", "500", "600", "700"],
    },
    {
      key: "border_radius", label: "Corner Radius", type: "select", tier: "basic",
      options: ["0px", "4px", "8px", "12px", "16px"],
    },
    {
      key: "transition_duration", label: "Animation Speed", type: "select", tier: "advanced",
      options: ["0ms", "100ms", "150ms", "250ms", "400ms"],
    },
    { key: "enable_hover_lift", label: "Hover Lift", type: "toggle", tier: "basic" },
  ];

  const TAB_STORAGE_KEY = "theme:editor_tab";
  const VALID_TABS = ["basic", "advanced", "palettes", "generate"];

  // Debounce for the generator's server round-trip. Long enough that
  // dragging a color picker doesn't fire a request per pixel, short enough
  // that letting go feels immediate.
  const GENERATE_DEBOUNCE_MS = 260;

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------
  function escapeAttr(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function toHexColor(value) {
    if (!value) return "#000000";
    const v = String(value).trim();
    if (/^#([0-9a-f]{3}){1,2}$/i.test(v)) {
      if (v.length === 4) return "#" + v.slice(1).split("").map((c) => c + c).join("");
      return v.toLowerCase();
    }
    return "#000000";
  }

  function slugify(s) {
    return String(s || "")
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function readStoredTab() {
    try {
      const v = localStorage.getItem(TAB_STORAGE_KEY);
      return VALID_TABS.includes(v) ? v : "basic";
    } catch (_e) { return "basic"; }
  }

  function writeStoredTab(tab) {
    try { localStorage.setItem(TAB_STORAGE_KEY, tab); } catch (_e) { /* non-fatal */ }
  }

  // ------------------------------------------------------------------
  // Contrast (mirror of Python theme/utils/contrast.py)
  // ------------------------------------------------------------------
  function hexToRgb(hex) {
    const h = toHexColor(hex).slice(1);
    return [
      parseInt(h.slice(0, 2), 16) / 255,
      parseInt(h.slice(2, 4), 16) / 255,
      parseInt(h.slice(4, 6), 16) / 255,
    ];
  }

  function luminance(hex) {
    const lin = (c) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
    const [r, g, b] = hexToRgb(hex).map(lin);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }

  function contrastRatio(fg, bg) {
    const l1 = luminance(fg);
    const l2 = luminance(bg);
    const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
    return (hi + 0.05) / (lo + 0.05);
  }

  // Walk the foreground hex toward black or white (whichever is farther
  // from the bg's luminance) until it passes AA. Returns the original
  // value if no passing shade is found within ~50 nudges.
  function nudgeToAA(fg, bg, target = 4.5) {
    if (contrastRatio(fg, bg) >= target) return fg;
    const bgLum = luminance(bg);
    const goDark = bgLum > 0.5; // bg is bright → push fg darker
    let [r, g, b] = hexToRgb(fg).map((c) => Math.round(c * 255));
    for (let i = 0; i < 50; i++) {
      r = goDark ? Math.max(0, r - 8) : Math.min(255, r + 8);
      g = goDark ? Math.max(0, g - 8) : Math.min(255, g + 8);
      b = goDark ? Math.max(0, b - 8) : Math.min(255, b + 8);
      const hex =
        "#" + [r, g, b].map((n) => n.toString(16).padStart(2, "0")).join("");
      if (contrastRatio(hex, bg) >= target) return hex;
      if ((goDark && r === 0 && g === 0 && b === 0) ||
          (!goDark && r === 255 && g === 255 && b === 255)) break;
    }
    return goDark ? "#000000" : "#ffffff";
  }

  // ------------------------------------------------------------------
  // Public mount point
  // ------------------------------------------------------------------
  // Editor never mutates global theme state directly — every change is
  // pushed through `opts.onPreview(overrides)` so the host (theme_switcher)
  // can re-render an in-dialog preview without touching the live page.
  // The active page only changes when the user clicks Apply.
  //
  //   opts.getSelectedTheme() : () => themeDict         (required)
  //   opts.onPreview(overrides) : (overrides) => void   (optional)
  window.openThemeEditor = function ($mount, parentDialog, opts) {
    const options = opts || {};
    const getSelectedTheme =
      typeof options.getSelectedTheme === "function"
        ? options.getSelectedTheme
        : () => (window.ThemeManager && ThemeManager.active) || {};
    const onPreview =
      typeof options.onPreview === "function" ? options.onPreview : () => {};

    const overrides = {};
    let activeTab = readStoredTab();
    let palettesCache = null; // lazy-loaded from server

    // ---- Generator state ----
    // Held in the closure rather than the DOM so switching tabs and coming
    // back restores the seed, polarity and results the user was looking at.
    // `genToken` discards responses from superseded requests: with a
    // debounced picker the replies can arrive out of order.
    let genSeed = null;
    let genDark = null;
    let genResults = null;
    let genSelected = null;
    let genBusy = false;
    let genError = null;
    let genToken = 0;
    let genTimer = null;

    const getBase = () => getSelectedTheme() || {};
    const valueFor = (key) => {
      const base = getBase();
      return overrides[key] != null ? overrides[key] : base[key];
    };

    const emitPreview = () => onPreview(Object.assign({}, overrides));

    // ---- Render orchestrator ----
    const render = () => {
      $mount.html(`
        <div class="theme-editor">
          <div class="theme-editor-tabs" role="tablist">
            ${tabBtnHTML("basic", "Basic")}
            ${tabBtnHTML("advanced", "Advanced")}
            ${tabBtnHTML("palettes", "Palettes")}
            ${tabBtnHTML("generate", "Generate")}
          </div>
          <div class="theme-editor-pane" data-pane></div>
          <div class="theme-editor-contrast" data-contrast></div>
        </div>
      `);
      bindTabs();
      renderPane();
      renderContrast();
    };

    const tabBtnHTML = (tab, label) => {
      const sel = tab === activeTab ? "is-active" : "";
      return `<button type="button" class="theme-editor-tab ${sel}"
                      data-tab="${tab}" role="tab"
                      aria-selected="${tab === activeTab}">${escapeAttr(__(label))}</button>`;
    };

    const bindTabs = () => {
      $mount.find(".theme-editor-tab").on("click", function () {
        const tab = this.dataset.tab;
        if (!VALID_TABS.includes(tab) || tab === activeTab) return;
        activeTab = tab;
        writeStoredTab(tab);
        render();
      });
    };

    // ---- Pane: Basic / Advanced / Palettes ----
    const renderPane = () => {
      const $pane = $mount.find("[data-pane]");
      if (activeTab === "palettes") {
        renderPalettes($pane);
        return;
      }
      if (activeTab === "generate") {
        renderGenerate($pane);
        return;
      }
      const tier = activeTab; // "basic" or "advanced"
      const visible = FIELDS.filter((f) => tier === "advanced" || f.tier === "basic");
      $pane.html(`
        <div class="theme-editor-grid">
          ${visible.map((f) => rowHTML(f, valueFor(f.key))).join("")}
        </div>
        <div class="theme-editor-hint">
          ${tier === "basic"
            ? __("Showing the most-used controls. Switch to Advanced for the full palette.")
            : __("Every theme token. Changes preview instantly.")}
        </div>
      `);
      $pane.find("[data-field]").on("input change", function () {
        const key = this.dataset.field;
        let value = this.type === "checkbox" ? (this.checked ? 1 : 0) : this.value;
        overrides[key] = value;
        emitPreview();
        renderContrast(); // update badge live
      });
    };

    const renderPalettes = ($pane) => {
      $pane.html(
        `<div class="theme-palettes-loading">${escapeAttr(__("Loading palettes…"))}</div>`
      );
      const apply = (palettes) => {
        if (!palettes.length) {
          $pane.html(
            `<div class="theme-editor-hint">${escapeAttr(__("No palettes available."))}</div>`
          );
          return;
        }
        $pane.html(`
          <div class="theme-palette-grid">
            ${palettes.map((p) => paletteCardHTML(p)).join("")}
          </div>
          <div class="theme-editor-hint">
            ${escapeAttr(__("Each palette is WCAG-AA verified. Click to fill all 11 colors at once."))}
          </div>
        `);
        $pane.find(".theme-palette-card").on("click", function () {
          const key = this.dataset.key;
          const p = palettes.find((x) => x.key === key);
          if (!p) return;
          applyPaletteColors(p);
          $pane.find(".theme-palette-card").removeClass("is-selected");
          this.classList.add("is-selected");
        });
      };

      if (palettesCache) {
        apply(palettesCache);
        return;
      }
      if (!window.frappe || !frappe.call) {
        apply([]);
        return;
      }
      frappe
        .call({ method: "nexus_theme.api.get_recommended_palettes" })
        .then((r) => {
          palettesCache = (r && r.message) || [];
          apply(palettesCache);
        })
        .catch(() => apply([]));
    };

    // ---- Pane: Generate from one brand color ----
    // Derivation lives server-side in utils/palette_generator.py so the
    // contrast maths has a single implementation. Applying a result writes
    // into the same `overrides` object the color pickers use, which is why
    // the Basic and Advanced tabs show the generated values immediately and
    // "Save as Custom Theme" needs no special case for it.
    const renderGenerate = ($pane) => {
      const base = getBase();
      if (genSeed == null) {
        genSeed = toHexColor(valueFor("accent") || "#4f46e5");
      }
      if (genDark == null) {
        const d = overrides.is_dark != null ? overrides.is_dark : base.is_dark;
        genDark = !!(d && d !== "0");
      }

      $pane.html(`
        <div class="theme-gen">
          <div class="theme-gen-controls">
            <label class="theme-gen-seed">
              <span>${escapeAttr(__("Brand color"))}</span>
              <span class="theme-gen-seed-inputs">
                <input type="color" data-gen-seed value="${escapeAttr(genSeed)}">
                <input type="text" data-gen-hex value="${escapeAttr(genSeed)}"
                       maxlength="7" spellcheck="false" autocomplete="off"
                       aria-label="${escapeAttr(__("Brand color hex value"))}">
              </span>
            </label>
            <div class="theme-gen-polarity" role="group"
                 aria-label="${escapeAttr(__("Polarity"))}">
              ${polarityBtnHTML("light", __("Light"), !genDark)}
              ${polarityBtnHTML("dark", __("Dark"), genDark)}
            </div>
          </div>
          <div data-gen-results></div>
          <div class="theme-editor-hint">
            ${escapeAttr(__("Every color is derived from your brand color and checked against WCAG AA. Pick a variant to load it into the editor — you can still adjust anything by hand afterwards."))}
          </div>
        </div>
      `);

      $pane.find("[data-gen-seed]").on("input", function () {
        genSeed = toHexColor(this.value);
        $pane.find("[data-gen-hex]").val(genSeed);
        scheduleGenerate();
      });

      $pane.find("[data-gen-hex]").on("input change", function () {
        const raw = String(this.value || "").trim();
        if (!/^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.test(raw)) return; // wait for a complete value
        genSeed = toHexColor(raw.startsWith("#") ? raw : "#" + raw);
        $pane.find("[data-gen-seed]").val(genSeed);
        scheduleGenerate();
      });

      $pane.find("[data-gen-polarity]").on("click", function () {
        const next = this.dataset.genPolarity === "dark";
        if (next === genDark) return;
        genDark = next;
        renderPane(); // repaint the segmented control, then refetch
        runGenerate();
      });

      // Opening the tab with nothing to show would read as broken, so the
      // first paint fetches immediately rather than waiting for input.
      if (genResults == null && !genBusy) runGenerate();
      else paintGenResults();
    };

    const polarityBtnHTML = (value, label, isOn) => `
      <button type="button" class="theme-gen-polarity-btn ${isOn ? "is-active" : ""}"
              data-gen-polarity="${value}" aria-pressed="${isOn}">${escapeAttr(label)}</button>`;

    const scheduleGenerate = () => {
      if (genTimer) clearTimeout(genTimer);
      genTimer = setTimeout(runGenerate, GENERATE_DEBOUNCE_MS);
    };

    // Drop the seed, polarity and cached results, and invalidate any request
    // still in flight so its reply cannot repaint a stale palette.
    const clearGeneratorState = () => {
      if (genTimer) clearTimeout(genTimer);
      genTimer = null;
      genToken++;
      genSeed = null;
      genDark = null;
      genResults = null;
      genSelected = null;
      genBusy = false;
      genError = null;
    };

    const runGenerate = () => {
      if (!window.frappe || !frappe.call) {
        genBusy = false;
        genResults = null;
        genError = __("Palette generation needs a server connection.");
        paintGenResults();
        return;
      }
      // Replies can land out of order once the picker is being dragged, so
      // only the newest request is allowed to write state.
      const token = ++genToken;
      genBusy = true;
      genError = null;
      paintGenResults();
      frappe
        .call({
          method: "nexus_theme.api.generate_palette",
          args: { seed: genSeed, is_dark: genDark ? 1 : 0 },
        })
        .then((r) => {
          if (token !== genToken) return;
          genBusy = false;
          genResults = (r && r.message) || [];
          genSelected = null;
          paintGenResults();
        })
        .catch(() => {
          if (token !== genToken) return;
          genBusy = false;
          genResults = null;
          genError = __("Could not generate a palette from that color.");
          paintGenResults();
        });
    };

    const paintGenResults = () => {
      const $r = $mount.find("[data-gen-results]");
      if (!$r.length) return;
      if (genBusy) {
        $r.html(`<div class="theme-palettes-loading">${escapeAttr(__("Generating…"))}</div>`);
        return;
      }
      if (genError) {
        $r.html(`<div class="theme-editor-hint">${escapeAttr(genError)}</div>`);
        return;
      }
      if (!genResults) {
        $r.html("");
        return;
      }
      if (!genResults.length) {
        $r.html(
          `<div class="theme-editor-hint">${escapeAttr(__("No accessible palette could be derived from that color."))}</div>`
        );
        return;
      }
      $r.html(`
        <div class="theme-palette-grid">
          ${genResults.map((p) => paletteCardHTML(p, p.key === genSelected)).join("")}
        </div>
      `);
      $r.find(".theme-palette-card").on("click", function () {
        const p = genResults.find((x) => x.key === this.dataset.key);
        if (!p) return;
        applyPaletteColors(p);
        genSelected = p.key;
        $r.find(".theme-palette-card").removeClass("is-selected");
        this.classList.add("is-selected");
      });
    };

    // Shared by the curated Palettes tab and the generator.
    //
    // `is_dark` travels with the colors on purpose. It is not a color, but
    // it drives the polarity attributes on <html>, and the Desk paints a lot
    // of chrome — sidebar, dropdowns, modals — from those. Applying a dark
    // color set while polarity still says "light" is what produced the black
    // sidebar over a light theme previously.
    const applyPaletteColors = (p) => {
      Object.assign(overrides, p.colors || {});
      if (p.is_dark != null) overrides.is_dark = p.is_dark ? 1 : 0;
      emitPreview();
      renderContrast();
    };

    const paletteCardHTML = (p, selected) => {
      const c = p.colors || {};
      return `
        <button type="button" class="theme-palette-card ${selected ? "is-selected" : ""}"
                data-key="${escapeAttr(p.key)}"
                title="${escapeAttr(p.description || p.label)}"
                aria-label="${escapeAttr(p.label)}">
          <div class="theme-palette-swatch"
               style="background:${escapeAttr(c.bg_primary)} !important;
                      border:1px solid ${escapeAttr(c.border)} !important;">
            <div class="tps-row" style="background:${escapeAttr(c.bg_surface)} !important;">
              <span class="tps-dot" style="background:${escapeAttr(c.accent)} !important;"></span>
              <span class="tps-text" style="color:${escapeAttr(c.text_primary)} !important;">Aa</span>
            </div>
            <div class="tps-btn"
                 style="background:${escapeAttr(c.button_bg)} !important;
                        color:${escapeAttr(c.button_text)} !important;">Action</div>
          </div>
          <div class="theme-palette-label">
            <span>${escapeAttr(p.label)}</span>
            <span class="theme-palette-tag">${escapeAttr(p.category || (p.is_dark ? "Dark" : "Light"))}</span>
          </div>
        </button>`;
    };

    // ---- Field row (color picker / select / toggle) ----
    const rowHTML = (f, val) => {
      if (f.type === "color") {
        return `
          <label class="theme-editor-row">
            <span>${escapeAttr(__(f.label))}</span>
            <input type="color" data-field="${f.key}" value="${escapeAttr(toHexColor(val))}">
          </label>`;
      }
      if (f.type === "toggle") {
        const checked = val ? "checked" : "";
        return `
          <label class="theme-editor-row">
            <span>${escapeAttr(__(f.label))}</span>
            <input type="checkbox" data-field="${f.key}" ${checked}>
          </label>`;
      }
      const opts = (f.options || [])
        .map((o) => `<option value='${escapeAttr(o)}' ${o === val ? "selected" : ""}>${escapeAttr(o)}</option>`)
        .join("");
      return `
        <label class="theme-editor-row">
          <span>${escapeAttr(__(f.label))}</span>
          <select data-field="${f.key}">${opts}</select>
        </label>`;
    };

    // ---- Live contrast badge ----
    // Three checks, mirroring theme_definition.py validation:
    //   1. text_primary on bg_primary  (AA, 4.5:1)
    //   2. text_primary on bg_surface  (AA, 4.5:1)
    //   3. button_text  on button_bg   (AA-large, 3.0:1)
    // The "worst" status sets the overall badge color.
    const renderContrast = () => {
      const $badge = $mount.find("[data-contrast]");
      if (!$badge.length) return;
      const v = (k) => valueFor(k);

      let pairs;
      try {
        pairs = [
          { label: __("Text on background"),  fg: v("text_primary"), bg: v("bg_primary"),  target: 4.5 },
          { label: __("Text on surface"),     fg: v("text_primary"), bg: v("bg_surface"),  target: 4.5 },
          { label: __("Button text on button"), fg: v("button_text"), bg: v("button_bg"),  target: 3.0 },
        ];
      } catch (_e) { return; }

      const rows = pairs.map((p) => {
        if (!p.fg || !p.bg) return { ...p, ratio: null, status: "unknown" };
        let ratio;
        try { ratio = contrastRatio(p.fg, p.bg); } catch (_e) { return { ...p, ratio: null, status: "unknown" }; }
        const status =
          ratio >= p.target ? "pass" : ratio >= p.target - 1.5 ? "warn" : "fail";
        return { ...p, ratio, status };
      });

      const overall = rows.some((r) => r.status === "fail")
        ? "fail"
        : rows.some((r) => r.status === "warn") ? "warn"
        : rows.every((r) => r.status === "pass") ? "pass" : "unknown";

      const icon = { pass: "✓", warn: "⚠", fail: "✕", unknown: "·" }[overall];
      const label = {
        pass:  __("Passes WCAG AA"),
        warn:  __("Marginal contrast"),
        fail:  __("Fails WCAG AA"),
        unknown: __("Contrast unknown"),
      }[overall];

      const showFix = overall !== "pass";
      $badge.html(`
        <div class="theme-contrast-badge is-${overall}">
          <span class="tcb-icon">${icon}</span>
          <span class="tcb-label">${escapeAttr(label)}</span>
          <div class="tcb-detail">
            ${rows.map((r) => `
              <div class="tcb-row tcb-row-${r.status}">
                <span>${escapeAttr(r.label)}</span>
                <span>${r.ratio == null ? "—" : r.ratio.toFixed(2) + ":1"}</span>
              </div>
            `).join("")}
          </div>
          ${showFix
            ? `<button type="button" class="tcb-fix btn btn-xs">${escapeAttr(__("Auto-fix"))}</button>`
            : ""}
        </div>
      `);
      if (showFix) $badge.find(".tcb-fix").on("click", autoFix);
    };

    // Nudge text_primary and button_text toward the nearest AA-passing
    // shade. Targets the worst-failing pair first. Persists into overrides
    // and previews immediately, mirroring the manual-edit flow.
    const autoFix = () => {
      const tp = valueFor("text_primary");
      const bp = valueFor("bg_primary");
      const bs = valueFor("bg_surface");
      const bt = valueFor("button_text");
      const bb = valueFor("button_bg");

      // Pick the bg that yields the worse contrast for text_primary
      const ratioOnPrimary = (() => { try { return contrastRatio(tp, bp); } catch (_e) { return null; } })();
      const ratioOnSurface = (() => { try { return contrastRatio(tp, bs); } catch (_e) { return null; } })();
      if (ratioOnPrimary != null && ratioOnSurface != null) {
        const worstBg = ratioOnPrimary < ratioOnSurface ? bp : bs;
        const fixed = nudgeToAA(tp, worstBg, 4.5);
        if (fixed !== tp) overrides.text_primary = fixed;
      }

      // Buttons need only AA-large (3.0)
      try {
        if (contrastRatio(bt, bb) < 3.0) {
          overrides.button_text = nudgeToAA(bt, bb, 3.0);
        }
      } catch (_e) { /* skip */ }

      emitPreview();
      // Refresh whichever pane is open so the picker swatches reflect new values
      renderPane();
      renderContrast();
      if (window.frappe && frappe.show_alert) {
        frappe.show_alert({
          message: __("Adjusted colors to meet WCAG AA"),
          indicator: "green",
        });
      }
    };

    // ---- Initial paint ----
    // The host (theme_switcher) drives refresh() whenever the selected
    // theme changes, so we don't subscribe to ThemeManager.onChange here —
    // that would re-render on the wrong trigger now that the live page is
    // not coupled to the dialog state.
    render();

    // ---- Public surface (consumed by theme_switcher.js) ----
    return {
      getOverrides: () => Object.assign({}, overrides),
      reset: () => {
        for (const k of Object.keys(overrides)) delete overrides[k];
        clearGeneratorState();
        render();
      },
      // Called by the host when a different theme is selected in the
      // gallery. The generator re-seeds from that theme rather than keeping
      // a seed the user chose for the previous one.
      refresh: () => {
        clearGeneratorState();
        render();
      },
      openSaveCustom: () => {
        const base = getBase();
        const suggested = base.theme_name ? base.theme_name + " (Custom)" : "My Theme";

        // Public sharing can be turned off site-wide in Theme Settings. The
        // server enforces it either way; hiding the checkbox just avoids
        // offering a control that would silently do nothing.
        const allowSharing = options.allowPublicSharing !== false;
        const saveFields = [
          { fieldtype: "Data", fieldname: "theme_name", label: __("Name"), reqd: 1, default: suggested },
        ];
        if (allowSharing) {
          saveFields.push({
            fieldtype: "Check",
            fieldname: "share_public",
            label: __("Share with other users"),
          });
        }

        const d = new frappe.ui.Dialog({
          title: __("Save as Custom Theme"),
          fields: saveFields,
          primary_action_label: __("Save"),
          primary_action: async (v) => {
            const name = (v.theme_name || "").trim();
            if (!name) return;
            const key = slugify(name);
            if (!key) {
              frappe.show_alert({ message: __("Name must contain letters or digits"), indicator: "orange" });
              return;
            }
            const payload = Object.assign({}, base, overrides, { theme_name: name, theme_key: key });
            delete payload.name;
            delete payload.is_default;
            delete payload.owner_user;

            try {
              const r = await frappe.call({
                method: "nexus_theme.api.save_custom_theme",
                args: { payload: JSON.stringify(payload), share_public: v.share_public ? 1 : 0 },
              });
              if (r && r.message && r.message.name) {
                await ThemeManager.setActive(r.message.name, {});
                frappe.show_alert({ message: __("Custom theme saved"), indicator: "green" });
              }
              d.hide();
              if (parentDialog) parentDialog.hide();
            } catch (err) {
              frappe.show_alert({
                message: __("Could not save theme: {0}", [err.message || ""]),
                indicator: "red",
              });
            }
          },
        });
        d.show();
      },
    };
  };
})();
