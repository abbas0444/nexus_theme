(function () {
  "use strict";

  // We deliberately use a different attribute than Frappe's `data-theme`
  // (which Frappe sets to "light"/"dark") so the two systems never clobber
  // each other. CSS in theme_variables.css scopes everything under
  // html[data-app-theme].
  const STORAGE_KEY = "theme:active";
  const APP_ATTR = "data-app-theme";
  const HOVER_ATTR = "data-hover-lift";
  // Exposes the active theme's polarity to CSS. Elevation has to be built
  // differently for each: on light surfaces depth reads as a dark hairline
  // plus a soft drop shadow, while on dark surfaces a black shadow is
  // invisible and the edge has to come from a light hairline instead.
  const DARK_ATTR = "data-app-dark";
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
      // Automatic light/dark pairing. `pair` holds the two themes the user
      // chose; `_systemQuery` is what decides which one is showing.
      this.mode = "Single";
      this.pair = { light: null, dark: null };
      this._systemQuery = null;
    }

    /** The theme that should be showing right now, given mode + system. */
    _resolvePair() {
      if (this.mode !== "Automatic" || !this.pair.dark) return this.pair.light;
      const prefersDark =
        this._systemQuery
          ? this._systemQuery.matches
          : window.matchMedia &&
            window.matchMedia("(prefers-color-scheme: dark)").matches;
      return prefersDark ? this.pair.dark : this.pair.light;
    }

    /**
     * Store the pair and start (or stop) following the OS setting.
     * Re-entrant: called on every load and after every save.
     */
    _setPair(mode, lightTheme, darkTheme) {
      this.mode = mode === "Automatic" && darkTheme ? "Automatic" : "Single";
      this.pair = { light: lightTheme || null, dark: darkTheme || null };

      if (this.mode !== "Automatic") {
        this._unwatchSystem();
        return;
      }
      this._watchSystem();
    }

    _watchSystem() {
      if (this._systemQuery || !window.matchMedia) return;
      this._systemQuery = window.matchMedia("(prefers-color-scheme: dark)");
      this._onSystemChange = () => {
        const next = this._resolvePair();
        if (next) this._crossfade(() => this._apply(next, this.overrides));
      };
      // addEventListener is unavailable on the legacy MediaQueryList in
      // older Safari, which only exposes addListener.
      if (this._systemQuery.addEventListener) {
        this._systemQuery.addEventListener("change", this._onSystemChange);
      } else if (this._systemQuery.addListener) {
        this._systemQuery.addListener(this._onSystemChange);
      }
    }

    _unwatchSystem() {
      if (!this._systemQuery || !this._onSystemChange) return;
      if (this._systemQuery.removeEventListener) {
        this._systemQuery.removeEventListener("change", this._onSystemChange);
      } else if (this._systemQuery.removeListener) {
        this._systemQuery.removeListener(this._onSystemChange);
      }
      this._systemQuery = null;
      this._onSystemChange = null;
    }

    bootstrapFromCache() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return;
        const cached = JSON.parse(raw);
        if (cached.mode === "Automatic" && cached.dark_theme) {
          this._setPair("Automatic", cached.light_theme, cached.dark_theme);
          const showing = this._resolvePair();
          if (showing) this._apply(showing, cached.overrides || {});
          return;
        }
        if (cached.theme) this._apply(cached.theme, cached.overrides || {});
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
          const r = await frappe.call({ method: "nexus_theme.api.get_active_theme" });
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
        this._setPair(result.mode, result.theme, result.dark_theme);
        const showing = this._resolvePair() || result.theme;
        this._apply(showing, result.overrides || {});
        this._cache(showing, result.overrides || {}, result);
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
        method: "nexus_theme.api.set_active_theme",
        args: {
          theme_name: themeName,
          overrides: JSON.stringify(overrides || {}),
        },
      });
      const r = await frappe.call({ method: "nexus_theme.api.get_active_theme" });
      if (r && r.message && r.message.theme) {
        const msg = r.message;
        this._setPair(msg.mode, msg.theme, msg.dark_theme);
        const showing = this._resolvePair() || msg.theme;
        this._crossfade(() => {
          this._apply(showing, msg.overrides || {});
          this._cache(showing, msg.overrides || {}, msg);
        });
      }
    }

    /**
     * Turn automatic light/dark pairing on or off.
     * `darkThemeName` is required when enabling.
     */
    async setThemeMode(mode, darkThemeName) {
      if (!window.frappe || !frappe.call) return;
      await frappe.call({
        method: "nexus_theme.api.set_theme_mode",
        args: { mode: mode, dark_theme: darkThemeName || null },
      });
      await this.loadFromServer();
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
          await frappe.call({ method: "nexus_theme.api.clear_active_theme" });
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

    /**
     * Frappe's own theme is taking over — the user picked Light / Dark /
     * Automatic in its Switch Theme dialog. Drop our theme locally right
     * away and record the choice on the server so it survives a reload.
     *
     * Recording it is the important part. An admin's site default theme
     * applies to every user without a preference of their own, so merely
     * deleting the preference would bring that default straight back on
     * the next load — which is what used to happen. clear_active_theme
     * now stores an explicit opt-out instead.
     *
     * Returns the server call so a caller can await it; local state is
     * already released by the time it returns. Safe to call repeatedly.
     */
    handOffToFrappe() {
      if (!this.active) return Promise.resolve();
      this._clearAppTheme();
      this._clearCache();
      this._notify();
      if (!(window.frappe && frappe.call)) return Promise.resolve();
      return frappe
        .call({ method: "nexus_theme.api.clear_active_theme" })
        .catch(() => {});
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
      // Reset before applying so stale variables from a previous theme
      // can never leak into the new one.
      for (const cssVar of Object.values(VAR_MAP)) {
        ROOT.style.removeProperty(cssVar);
      }
      const merged = Object.assign({}, theme, overrides);
      // Hover lift is not in VAR_MAP (it's an attribute, not a variable), so
      // it has to be read off `merged` — reading it off `theme` would ignore
      // the editor's override and leave the toggle inert. Compare against
      // "0" explicitly: a cached override can arrive as a numeric string.
      const hoverLift = merged.enable_hover_lift;
      ROOT.setAttribute(
        HOVER_ATTR,
        hoverLift && hoverLift !== "0" ? "1" : "0"
      );
      const isDark = !!(merged.is_dark && merged.is_dark !== "0");
      ROOT.setAttribute(DARK_ATTR, isDark ? "1" : "0");
      // Align Frappe's own polarity with the theme's.
      //
      // Frappe defines ~70 design tokens twice — once on :root and again
      // under [data-theme="dark"] — and we only remap about 20 of them.
      // The rest keep whatever polarity `data-theme` says. Leaving it on
      // "dark" while a light theme paints the page produced a light Desk
      // with a black sidebar and black dropdowns, because every unmapped
      // token was still resolving to its dark value (and the mirror image
      // on the other side).
      //
      // Setting it here fixes all of them at once, including tokens added
      // by future Frappe versions. Safe with respect to our own observer:
      // _watchFrappeToggle() filters on `data-theme-mode`, and Frappe's
      // observer in desk.js filters on the same — neither reacts to
      // `data-theme`, so this cannot loop.
      ROOT.setAttribute("data-theme", isDark ? "dark" : "light");
      for (const [field, cssVar] of Object.entries(VAR_MAP)) {
        const v = merged[field];
        if (v != null && v !== "") ROOT.style.setProperty(cssVar, String(v));
      }
      this._notify();
    }

    _clearAppTheme() {
      this.active = null;
      this.overrides = {};
      // Stop following the OS setting — otherwise a system change would
      // re-apply a theme we have just stepped away from.
      this._unwatchSystem();
      this.mode = "Single";
      this.pair = { light: null, dark: null };
      ROOT.removeAttribute(APP_ATTR);
      ROOT.removeAttribute(HOVER_ATTR);
      ROOT.removeAttribute(DARK_ATTR);
      // Hand `data-theme` back to Frappe rather than guessing: its own
      // resolver knows how to expand "automatic" via the media query.
      if (window.frappe && frappe.ui && typeof frappe.ui.set_theme === "function") {
        try {
          frappe.ui.set_theme();
        } catch (_e) {
          /* fall through to the manual derivation below */
        }
      } else {
        const mode = ROOT.getAttribute("data-theme-mode") || "light";
        ROOT.setAttribute("data-theme", mode === "automatic" ? "light" : mode);
      }
      for (const cssVar of Object.values(VAR_MAP)) {
        ROOT.style.removeProperty(cssVar);
      }
    }

    _cache(theme, overrides, pairInfo) {
      try {
        const payload = { theme, overrides: overrides || {} };
        // Cache the pair as well as the resolved theme, so a reload with the
        // OS in the other mode paints the correct side immediately instead
        // of flashing the previous one until the server responds.
        if (pairInfo && pairInfo.mode === "Automatic" && pairInfo.dark_theme) {
          payload.mode = "Automatic";
          payload.light_theme = pairInfo.theme;
          payload.dark_theme = pairInfo.dark_theme;
        }
        localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
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
     * Watch the two attributes Frappe itself writes on <html>.
     *
     * `data-theme-mode` is written by its Switch Theme dialog. While one
     * of our themes is showing that is the user asking for Frappe's, so
     * we step aside — anything else has two systems fighting over the
     * same surfaces.
     *
     * `data-theme` is written by Frappe's own resolver (desk.js on boot,
     * and its OS listener when the mode is "automatic"). Our themes are
     * single-polarity and _apply() pins this attribute to match; if
     * Frappe flips it underneath us the ~50 tokens we don't remap swing
     * to the wrong side, so it is put back.
     */
    _watchFrappeToggle() {
      if (this._frappeObserver || typeof MutationObserver === "undefined") return;
      this._frappeObserver = new MutationObserver((records) => {
        for (const rec of records) {
          if (rec.attributeName === "data-theme-mode") this._onFrappeModeWrite();
          else if (rec.attributeName === "data-theme") this._onFrappeThemeWrite();
        }
      });
      this._frappeObserver.observe(ROOT, {
        attributes: true,
        attributeFilter: ["data-theme-mode", "data-theme"],
      });
    }

    _onFrappeModeWrite() {
      const next = ROOT.getAttribute("data-theme-mode") || "light";
      const changed = next !== this.frappeMode;
      this.frappeMode = next;
      if (!this.active) {
        if (changed) this._notify();
        return;
      }
      // Step aside whether or not the value moved. Frappe's dialog writes
      // the attribute even when it is unchanged — and "Frappe Light" while
      // the mode is already light is the common case when one of our dark
      // themes is sitting on top of it. Bailing out on an unchanged value
      // is exactly what used to leave that dark theme in place.
      this.handOffToFrappe();
    }

    _onFrappeThemeWrite() {
      if (!this.active) return;
      const want = ROOT.getAttribute(DARK_ATTR) === "1" ? "dark" : "light";
      if (ROOT.getAttribute("data-theme") !== want) {
        ROOT.setAttribute("data-theme", want);
      }
      // No loop: the write above lands here again, matches, and stops.
      // Frappe's observer in desk.js filters on `data-theme-mode` only.
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
