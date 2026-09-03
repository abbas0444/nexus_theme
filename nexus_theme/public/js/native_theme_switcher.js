(function () {
  "use strict";

  // ------------------------------------------------------------------
  // Extend Frappe's built-in "Switch Theme" dialog (sidebar → Display →
  // Toggle Theme, or Shift+Ctrl+G) so it lists every Theme Definition
  // alongside Frappe's own Light / Dark / Automatic.
  //
  // We subclass rather than patch so core's keyboard navigation,
  // selection handling and markup keep working untouched. Only three
  // things change:
  //   fetch_themes()     — append our themes to the native three
  //   get_preview_html() — native themes fall through to super(); ours
  //                        render the same markup with theme colors
  //                        pushed in as inline CSS variables
  //   toggle_theme()     — native themes fall through to super(); ours
  //                        route through ThemeManager instead
  //
  // Interaction with theme_manager.js: picking a native theme hands the
  // Desk back to Frappe explicitly (ThemeManager.handOffToFrappe) before
  // core's own handler runs. The manager's observer on `data-theme-mode`
  // is a backstop for other entry points, not the mechanism — core writes
  // that attribute even when the value is unchanged, and the user picking
  // the native mode that is already set is the common case. We never
  // touch `data-theme-mode` when applying one of our own themes.
  // ------------------------------------------------------------------

  const HEX_RE = /^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/;
  const LENGTH_RE = /^\d+(?:\.\d+)?(?:px|rem|em|%)$/;

  // Theme Definition values are validated server-side (css_safety.py), but
  // these land in a style="" attribute — re-check here rather than trust the
  // payload, since a public theme is authored by another user.
  function safeColor(value, fallback) {
    const v = String(value == null ? "" : value).trim();
    return HEX_RE.test(v) ? v : fallback;
  }

  function safeLength(value, fallback) {
    const v = String(value == null ? "" : value).trim();
    return LENGTH_RE.test(v) ? v : fallback;
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

  function install() {
    if (!window.frappe || !frappe.ui || !frappe.ui.ThemeSwitcher) return false;
    if (frappe.ui.ThemeSwitcher.__nxt_extended) return true;

    const Base = frappe.ui.ThemeSwitcher;

    class NexusThemeSwitcher extends Base {
      setup_dialog() {
        super.setup_dialog();
        // The native dialog is sized for exactly three cards. Widen it and
        // tag it so our CSS can switch the grid to a scrollable multi-row
        // layout without affecting any other dialog.
        this.dialog.$wrapper.find(".modal-dialog").addClass("modal-lg");
        this.dialog.$wrapper.addClass("nxt-theme-switcher");
      }

      refresh() {
        // A Theme Definition being active wins over `data-theme-mode`: the
        // latter still reads "light"/"dark" while our CSS variables are what
        // is actually painting the Desk.
        const active = (window.ThemeManager && ThemeManager.active) || null;
        this.current_theme =
          (active && active.name) ||
          document.documentElement.getAttribute("data-theme-mode") ||
          "light";
        this.fetch_themes().then(() => this.render());
      }

      fetch_themes() {
        return super.fetch_themes().then((native) => {
          // Group the native three so they read as one block once ours are
          // appended below them.
          native.forEach((t) => {
            t.group = __("Frappe");
          });

          if (!window.frappe || !frappe.call) {
            this.themes = native;
            return this.themes;
          }

          return frappe
            .call({ method: "nexus_theme.api.get_available_themes" })
            .then((r) => {
              const data = (r && r.message) || {};
              const groups = [
                [__("Default Themes"), data.defaults],
                [__("My Custom Themes"), data.owned],
                [__("Shared by Others"), data.public],
              ];

              const custom = [];
              for (const [group, list] of groups) {
                for (const def of list || []) {
                  // Never let a Theme Definition whose key collides with a
                  // native mode shadow it — the native one must keep working.
                  if (["light", "dark", "automatic"].includes(def.name)) continue;
                  custom.push({
                    name: def.name,
                    label: def.theme_name || def.name,
                    info: def.is_dark ? __("Dark Theme") : __("Light Theme"),
                    group: group,
                    is_custom: true,
                    def: def,
                  });
                }
              }

              this.themes = native.concat(custom);
              return this.themes;
            })
            .catch(() => {
              // Permission or network failure — degrade to the native three
              // rather than leaving the user with an empty dialog.
              this.themes = native;
              return this.themes;
            });
        });
      }

      render() {
        // Core appends without clearing; we clear because refresh() can run
        // again after a theme is applied.
        this.body.empty();
        let last_group = null;
        this.themes.forEach((theme) => {
          if (theme.group && theme.group !== last_group) {
            last_group = theme.group;
            $(
              `<div class="nxt-theme-group">${escapeHtml(theme.group)}</div>`
            ).appendTo(this.body);
          }
          const html = this.get_preview_html(theme);
          html.appendTo(this.body);
          theme.$html = html;
        });
      }

      get_preview_html(theme) {
        if (!theme.is_custom) return super.get_preview_html(theme);

        const t = theme.def || {};
        const bg = safeColor(t.bg_primary, "#ffffff");
        const surface = safeColor(t.bg_surface, "#f7f8fa");
        const text = safeColor(t.text_primary, "#1f2937");
        const muted = safeColor(t.text_muted, "#6b7280");
        const accent = safeColor(t.accent, "#4f46e5");
        const button = safeColor(t.button_bg, accent);
        const border = safeColor(t.border, "#e5e7eb");
        const radius = safeLength(t.border_radius, "8px");

        // Remap the Frappe tokens that theme_switcher.scss reads, scoped to
        // this one swatch. `.background` and its children inherit them, so
        // core's stylesheet paints our colors with no CSS of our own.
        const style = [
          `--bg-color:${bg}`,
          `--card-bg:${surface}`,
          `--subtle-accent:${surface}`,
          `--bg-light-gray:${surface}`,
          `--text-on-light-gray:${text}`,
          `--primary-color:${button}`,
          `--text-light:${muted}`,
          `--text-color:${text}`,
          `--nxt-preview-border:${border}`,
          `--border-radius-lg:${radius}`,
        ].join(";");

        const selected = this.current_theme === theme.name ? "selected" : "";
        const preview = $(`<div class="${selected}">
			<div class="nxt-theme-preview" title="${escapeHtml(theme.info)}" style="${style}">
				<div class="background">
					<div>
						<div class="preview-check">
							${frappe.utils.icon("tick", "xs")}
						</div>
					</div>
					<div class="navbar"></div>
					<div class="p-2">
						<div class="toolbar">
							<span class="text"></span>
							<span class="primary"></span>
						</div>
						<div class="foreground"></div>
						<div class="foreground"></div>
					</div>
				</div>
			</div>
			<div class="mt-3 text-center">
				<h5 class="theme-title">${escapeHtml(theme.label)}</h5>
			</div>
		</div>`);

        preview.on("click", () => {
          if (this.current_theme === theme.name) return;
          this.themes.forEach((th) => {
            if (th.$html) th.$html.removeClass("selected");
          });
          preview.addClass("selected");
          this.toggle_theme(theme.name);
        });

        return preview;
      }

      toggle_theme(name) {
        const theme = (this.themes || []).find((t) => t.name === name);
        if (!theme || !theme.is_custom) {
          // Light / Dark / Automatic. Release our theme first so the
          // manager's observer sees nothing active when core writes
          // `data-theme-mode` a moment later, and only one clear reaches
          // the server. Core then persists desk_theme and Frappe's own
          // resolver derives `data-theme` from the new mode.
          if (window.ThemeManager && ThemeManager.active) {
            ThemeManager.handOffToFrappe();
          }
          return super.toggle_theme(name);
        }

        if (!window.ThemeManager) {
          frappe.show_alert({
            message: __("Theme manager is not available"),
            indicator: "red",
          });
          return;
        }

        this.current_theme = name;
        return Promise.resolve(ThemeManager.setActive(name, {}))
          .then(() => {
            frappe.show_alert({ message: __("Theme Changed"), indicator: "green" });
          })
          .catch(() => {
            frappe.show_alert({
              message: __("Could not apply theme"),
              indicator: "red",
            });
          });
      }
    }

    NexusThemeSwitcher.__nxt_extended = true;
    frappe.ui.ThemeSwitcher = NexusThemeSwitcher;
    return true;
  }

  // Every entry point (sidebar Display menu, the Shift+Ctrl+G shortcut, the
  // "Toggle Theme" Navbar Item) constructs a fresh `new frappe.ui.ThemeSwitcher()`
  // at click time, so swapping the class at any point before the first click is
  // enough — there is no long-lived instance to replace.
  if (!install()) {
    let attempts = 0;
    const retry = () => {
      if (install()) return;
      if (attempts++ < 40) setTimeout(retry, 250);
    };
    if (window.frappe && typeof frappe.ready === "function") {
      frappe.ready(retry);
    } else {
      document.addEventListener("DOMContentLoaded", retry);
    }
  }
})();
