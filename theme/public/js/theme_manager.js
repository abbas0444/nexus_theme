(function () {
  "use strict";

  // We deliberately use a different attribute than Frappe's `data-theme`
  // (which Frappe sets to "light"/"dark") so the two systems never clobber
  // each other. CSS in theme_variables.css scopes everything under
  // html[data-app-theme].
  const STORAGE_KEY = "theme:active";
  const APP_ATTR = "data-app-theme";
  const HOVER_ATTR = "data-hover-lift";
  const ROOT = document.documentElement;

  const VAR_MAP = {
    bg_primary: "--theme-bg-primary",
    bg_surface: "--theme-bg-surface",
    bg_input: "--theme-bg-input",
    text_primary: "--theme-text-primary",
    text_muted: "--theme-text-muted",
    accent: "--theme-accent",
    accent_hover: "--theme-accent-hover",
    button_bg: "--theme-button-bg",
    button_text: "--theme-button-text",
    button_hover_bg: "--theme-button-hover-bg",
    border: "--theme-border",
    font_family: "--theme-font-family",
    font_size_base: "--theme-font-size-base",
    font_weight_base: "--theme-font-weight-base",
    transition_duration: "--theme-transition-duration",
    border_radius: "--theme-border-radius",
  };

  class ThemeManager {
    constructor() {
      this.active = null;
      this.overrides = {};
      this.frappeMode = ROOT.getAttribute("data-theme-mode") || "light";
      this._listeners = new Set();
      this._frappeObserver = null;
    }

    bootstrapFromCache() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return;
        const { theme, overrides } = JSON.parse(raw);
        if (theme) this._apply(theme, overrides || {});
      } catch (_e) {
        /* ignore malformed cache */
      }
    }

    async loadFromServer() {
      // `frappe.boot` is cached per-user in Redis on the server, so
      // `frappe.boot.active_theme` can arrive stale (`from_cache === 1`)
      // right after the user saved a new theme. In that case we MUST
      // bypass the boot value and ask the server directly — otherwise
      // the freshly-applied theme reverts to the previous one on refresh.
      const fromCache = !!(window.frappe && frappe.boot && frappe.boot.from_cache);
      let result = null;

      if (window.frappe && frappe.call) {
        try {
          const r = await frappe.call({ method: "theme.api.get_active_theme" });
          result = r && r.message;
        } catch (_e) {
          // Network / permission failure — fall back to whatever boot gave us
          // (better than blowing away the user's theme), but only if it's not
          // explicitly a cached boot. A cached boot + failed call means we
          // genuinely don't know — keep the localStorage paint and bail.
          if (fromCache) return;
          const boot = frappe.boot && frappe.boot.active_theme;
          if (boot === undefined) return;
          result = boot;
        }
      } else {
        const boot = window.frappe && frappe.boot && frappe.boot.active_theme;
        if (boot === undefined) return;
        result = boot;
      }

      if (result && result.theme) {
        this._apply(result.theme, result.overrides || {});
        this._cache(result.theme, result.overrides || {});
      } else {
        // Server says "no custom theme" — clear local state so Frappe's
        // native palette renders without our variables interfering.
        this._clearAppTheme();
        this._clearCache();
        this._notify();
      }
    }

    async setActive(themeName, overrides = {}) {
      if (!window.frappe || !frappe.call) return;
      await frappe.call({
        method: "theme.api.set_active_theme",
        args: {
          theme_name: themeName,
          overrides: JSON.stringify(overrides || {}),
        },
      });
      const r = await frappe.call({ method: "theme.api.get_active_theme" });
      if (r && r.message && r.message.theme) {
        this._crossfade(() => {
          this._apply(r.message.theme, r.message.overrides || {});
          this._cache(r.message.theme, r.message.overrides || {});
        });
      }
    }

    previewOverrides(partial) {
      if (!this.active) return;
      const merged = Object.assign({}, this.overrides, partial || {});
      this._apply(this.active, merged);
    }

    applyThemeLocal(theme) {
      if (!theme) return;
      // Live preview from the gallery: never carry forward the previous
      // theme's user overrides — they belong to that theme, not this one.
      this._apply(theme, {});
    }

    /**
     * Reset to Frappe Light:
     * 1. Clear our custom theme on the server.
     * 2. Persist Frappe's own preference as Light (so the built-in toggle agrees).
     * 3. Wipe local state so Frappe's stock palette paints cleanly.
     */
    async resetToFrappeDefault() {
      if (window.frappe && frappe.call) {
        try {
          await frappe.call({ method: "theme.api.clear_active_theme" });
        } catch (_e) {
          /* still clear client state below */
        }
      }
      try {
        if (window.frappe && frappe.xcall) {
          await frappe.xcall(
            "frappe.core.doctype.user.user.switch_theme",
            { theme: "Light" }
          );
        }
      } catch (_e) {
        /* non-fatal */
      }
      this._crossfade(() => {
        this._clearAppTheme();
        this._clearCache();
        // Align Frappe's own attributes with Light so its CSS picks up the
        // light palette without us having to fight it.
        ROOT.setAttribute("data-theme-mode", "light");
        ROOT.setAttribute("data-theme", "light");
        this.frappeMode = "light";
        this._notify();
      });
    }

    // Brief opacity dip on the body while we swap CSS variables. Only used
    // for committed changes (setActive, reset) — live preview is silent.
    // Honors prefers-reduced-motion via the CSS guard in theme_variables.css.
    _crossfade(applyFn) {
      const body = document.body;
      if (!body || typeof applyFn !== "function") {
        if (typeof applyFn === "function") applyFn();
        return;
      }
      body.classList.add("theme-switching");
      // Let the dip render one frame, then swap, then lift the dip.
      requestAnimationFrame(() => {
        applyFn();
        setTimeout(() => body.classList.remove("theme-switching"), 220);
      });
    }

    onChange(fn) {
      this._listeners.add(fn);
      return () => this._listeners.delete(fn);
    }

    _apply(theme, overrides) {
      this.active = theme;
      this.overrides = overrides || {};
      // Theme variables live on <html> only. The Theme Studio dialog
      // carries the `theme-studio-isolated` class, and CSS in
      // theme_switcher.css redeclares every themed variable inside that
      // subtree — so the dialog never picks up the active theme even
      // though it inherits from <html>. We do NOT touch any element
      // tagged `theme-studio-isolated` here, ever.
      ROOT.setAttribute(APP_ATTR, theme.theme_key || "custom");
      ROOT.setAttribute(HOVER_ATTR, theme.enable_hover_lift ? "1" : "0");
      // Reset before applying so stale variables from a previous theme
      // can never leak into the new one.
      for (const cssVar of Object.values(VAR_MAP)) {
        ROOT.style.removeProperty(cssVar);
      }
      const merged = Object.assign({}, theme, overrides);
      for (const [field, cssVar] of Object.entries(VAR_MAP)) {
        const v = merged[field];
        if (v != null && v !== "") ROOT.style.setProperty(cssVar, String(v));
      }
      this._notify();
    }

    _clearAppTheme() {
      this.active = null;
      this.overrides = {};
      ROOT.removeAttribute(APP_ATTR);
      ROOT.removeAttribute(HOVER_ATTR);
      for (const cssVar of Object.values(VAR_MAP)) {
        ROOT.style.removeProperty(cssVar);
      }
    }

    _cache(theme, overrides) {
      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({ theme, overrides: overrides || {} })
        );
      } catch (_e) {
        /* quota or disabled — non-fatal */
      }
    }

    _clearCache() {
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch (_e) {
        /* non-fatal */
      }
    }

    _notify() {
      for (const fn of this._listeners) {
        try {
          fn(this.active, this.overrides, this.frappeMode);
        } catch (_e) {
          /* ignore listener errors */
        }
      }
    }

    /**
     * When the user picks a theme from Frappe's built-in toggle, Frappe
     * mutates `data-theme-mode` on <html>. We watch that and drop our
     * custom theme so Frappe's native palette is what renders — anything
     * else would have two systems fighting on the same surfaces.
     */
    _watchFrappeToggle() {
      if (this._frappeObserver || typeof MutationObserver === "undefined") return;
      this._frappeObserver = new MutationObserver(() => {
        const next = ROOT.getAttribute("data-theme-mode") || "light";
        if (next === this.frappeMode) return;
        this.frappeMode = next;
        if (!this.active) {
          this._notify();
          return;
        }
        // Frappe took over → step aside. Clear local state and let the
        // server forget our preference too (best effort, non-blocking).
        this._clearAppTheme();
        this._clearCache();
        if (window.frappe && frappe.call) {
          frappe
            .call({ method: "theme.api.clear_active_theme" })
            .catch(() => {});
        }
        this._notify();
      });
      this._frappeObserver.observe(ROOT, {
        attributes: true,
        attributeFilter: ["data-theme-mode"],
      });
    }
  }

  const mgr = new ThemeManager();
  window.ThemeManager = mgr;

  mgr.bootstrapFromCache();
  mgr._watchFrappeToggle();

  window.addEventListener("storage", (e) => {
    if (e.key !== STORAGE_KEY) return;
    if (!e.newValue) {
      mgr._clearAppTheme();
      mgr._notify();
      return;
    }
    try {
      const { theme, overrides } = JSON.parse(e.newValue);
      if (theme) mgr._apply(theme, overrides || {});
    } catch (_err) {
      /* ignore */
    }
  });

  const reconcile = () => mgr.loadFromServer();
  if (window.frappe && typeof frappe.ready === "function") {
    frappe.ready(reconcile);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", reconcile);
  } else {
    reconcile();
  }
})();
