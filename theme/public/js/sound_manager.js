(function () {
  "use strict";

  const CAP_MS = 3000; // Every sound cut at 3 seconds regardless of file length.

  // Some user-facing event names are not the same as the internal key Frappe
  // uses when calling play_sound. The Save button, for example, fires
  // play_sound("click") on success (form.js:766) — there is no "save" sound
  // in Frappe core. We alias those here so a user upload for "save" actually
  // overrides the audio element Frappe plays.
  const USER_TO_FRAPPE = {
    save: "click",
  };

  function frappeKeyFor(userKey) {
    return USER_TO_FRAPPE[userKey] || userKey;
  }

  class SoundManager {
    constructor() {
      this.enabled = true;
      this.mapping = {}; // { user_event_key: { url, volume } }
      this._listeners = new Set();
      this._patched = false;
    }

    /**
     * Given a Frappe-internal key (what play_sound was called with), find the
     * user's configured entry — checking the direct key first, then any user
     * key that aliases to this Frappe key.
     */
    _lookup(frappeKey) {
      if (this.mapping[frappeKey]) return this.mapping[frappeKey];
      for (const [userKey, def] of Object.entries(this.mapping)) {
        if (frappeKeyFor(userKey) === frappeKey) return def;
      }
      return null;
    }

    volumeFor(name) {
      const m = this._lookup(name);
      if (m && typeof m.volume === "number") return m.volume;
      const el = document.getElementById("sound-" + name);
      const v = el && parseFloat(el.getAttribute("volume"));
      return Number.isFinite(v) ? v : 0.5;
    }

    /** Swap the src of Frappe's `<audio id="sound-X">` elements with user uploads. */
    applyMapping(mapping) {
      this.mapping = mapping || {};
      for (const [userKey, def] of Object.entries(this.mapping)) {
        if (!def || !def.url) continue;
        const frappeKey = frappeKeyFor(userKey);
        const el = document.getElementById("sound-" + frappeKey);
        if (el) {
          el.src = def.url;
          el.load && el.load();
        }
      }
      this._notify();
    }

    resetMappingFor(name) {
      delete this.mapping[name];
      // We can't restore the original Frappe src here (it's not tracked),
      // but a page reload will re-render with defaults.
      this._notify();
    }

    setEnabled(v) {
      this.enabled = !!v;
      this._notify();
    }

    onChange(fn) {
      this._listeners.add(fn);
      return () => this._listeners.delete(fn);
    }

    _notify() {
      for (const fn of this._listeners) {
        try {
          fn(this);
        } catch (_e) {
          /* ignore */
        }
      }
    }

    /** Wrap frappe.utils.play_sound: enforce enabled flag, volume, 3-second cap. */
    patchPlaySound() {
      if (this._patched) return;
      if (!window.frappe || !frappe.utils) return;
      const self = this;
      frappe.utils.play_sound = function (name) {
        if (!self.enabled) return;
        if (window.frappe && frappe.boot && frappe.boot.user && frappe.boot.user.mute_sounds) {
          return;
        }
        const audio = document.getElementById("sound-" + name);
        if (!audio) return;
        try {
          audio.pause();
          audio.currentTime = 0;
          const vol = self.volumeFor(name);
          if (Number.isFinite(vol)) audio.volume = Math.max(0, Math.min(1, vol));
          const p = audio.play();
          if (p && typeof p.catch === "function") p.catch(() => {});
          clearTimeout(audio.__capTimer);
          audio.__capTimer = setTimeout(() => {
            try {
              if (!audio.paused) {
                audio.pause();
                audio.currentTime = 0;
              }
            } catch (_e) {
              /* ignore */
            }
          }, CAP_MS);
        } catch (_e) {
          /* ignore */
        }
      };
      this._patched = true;
    }

    /**
     * Frappe's mandatory-field validation popup (form/save.js) is a plain
     * msgprint with title "Missing Fields" — it has no play_sound call.
     * Wrap frappe.msgprint so that title triggers our "missing_fields" sound.
     */
    wireMissingFieldsSound() {
      if (!window.frappe || typeof frappe.msgprint !== "function") return;
      if (frappe.msgprint.__sm_wrapped) return;
      const orig = frappe.msgprint;
      const wrapped = function (msg) {
        try {
          const title = msg && typeof msg === "object" ? msg.title : null;
          const t = typeof title === "string" ? title : (title && title.toString && title.toString()) || "";
          if (t === "Missing Fields" || t === __("Missing Fields")) {
            if (frappe.utils && frappe.utils.play_sound) {
              frappe.utils.play_sound("missing_fields");
            }
          }
        } catch (_e) {
          /* ignore — never block the original msgprint */
        }
        return orig.apply(this, arguments);
      };
      wrapped.__sm_wrapped = true;
      frappe.msgprint = wrapped;
    }

    /** Hook new realtime notifications to play the (new) 'notification' sound. */
    wireRealtimeNotification() {
      if (!window.frappe || !frappe.realtime || !frappe.realtime.on) return;
      frappe.realtime.on("notification", () => {
        if (window.frappe && frappe.utils && frappe.utils.play_sound) {
          frappe.utils.play_sound("notification");
        }
      });
    }

    /**
     * Detect a fresh login with two strategies:
     *   1. document.referrer — if we came from /login, always play.
     *   2. sessionStorage flag — first desk load of a tab that has no referrer info.
     * The flag is cleared on logout so a same-tab logout→login replays the sound.
     */
    wireLoginSound() {
      let shouldPlay = false;
      try {
        const ref = (document.referrer || "").toString();
        const cameFromLogin =
          ref.includes("/login") || ref.endsWith("/login");
        const flag = sessionStorage.getItem("theme:login_sound_played");
        if (cameFromLogin) {
          shouldPlay = true;
          sessionStorage.setItem("theme:login_sound_played", "1");
        } else if (!flag) {
          shouldPlay = true;
          sessionStorage.setItem("theme:login_sound_played", "1");
        }
      } catch (_e) {
        /* storage unavailable — fall through silently */
      }
      if (!shouldPlay) return;

      // Login fires on first page load — the <audio id="sound-login"> element
      // still has Frappe's default src preloaded, and our applyMapping src
      // swap is async (load() kicks off a fetch that won't be done in 250ms).
      // Bypass the audio element entirely: if the user has a custom login
      // URL, play it via a one-shot Audio() with the same 3-second cap as
      // the global play_sound. Falls back to play_sound("login") otherwise.
      const playCustomOrDefault = () => {
        if (!this.enabled) return;
        if (
          window.frappe &&
          frappe.boot &&
          frappe.boot.user &&
          frappe.boot.user.mute_sounds
        ) {
          return;
        }
        const def = this.mapping && this.mapping.login;
        if (def && def.url) {
          try {
            const a = new Audio(def.url);
            const v = typeof def.volume === "number" ? def.volume : 0.5;
            a.volume = Math.max(0, Math.min(1, v));
            const p = a.play();
            if (p && typeof p.catch === "function") p.catch(() => {});
            setTimeout(() => {
              try {
                if (!a.paused) {
                  a.pause();
                  a.currentTime = 0;
                }
              } catch (_e) {
                /* ignore */
              }
            }, CAP_MS);
            return;
          } catch (_e) {
            /* fall through to default */
          }
        }
        if (window.frappe && frappe.utils && frappe.utils.play_sound) {
          frappe.utils.play_sound("login");
        }
      };

      setTimeout(playCustomOrDefault, 250);
    }

    /**
     * Play the logout sound before Frappe navigates away. Multiple strategies
     * because Frappe's logout plumbing varies by version — we hook all three:
     *   (a) frappe.app.logout (older)
     *   (b) frappe.call({method: "logout"}) (current)
     *   (c) clicks on any /logout link or "Logout" menu item (fallback)
     * Each path plays the sound, clears the login flag, and delays the
     * navigation ~400ms so the audio has a chance to start.
     */
    wireLogoutSound() {
      let firing = false;
      const fireAndClear = () => {
        if (firing) return;
        firing = true;
        try {
          sessionStorage.removeItem("theme:login_sound_played");
        } catch (_e) {
          /* ignore */
        }
        if (window.frappe && frappe.utils && frappe.utils.play_sound) {
          frappe.utils.play_sound("logout");
        }
        setTimeout(() => {
          firing = false;
        }, 500);
      };

      // (a) Wrap frappe.app.logout if it exists.
      if (window.frappe && frappe.app && typeof frappe.app.logout === "function") {
        const orig = frappe.app.logout.bind(frappe.app);
        frappe.app.logout = function () {
          fireAndClear();
          return new Promise((resolve) => {
            setTimeout(() => {
              try {
                resolve(orig());
              } catch (_e) {
                resolve();
              }
            }, 400);
          });
        };
      }

      // (b) Intercept frappe.call for the logout RPC. This is the most reliable
      // hook in modern Frappe because the user menu calls logout via frappe.call
      // regardless of which wrapper function triggered it.
      if (window.frappe && typeof frappe.call === "function") {
        const origCall = frappe.call;
        frappe.call = function (opts) {
          const method =
            (opts && (opts.method || opts.cmd)) ||
            (typeof opts === "string" ? opts : "");
          if (
            method === "logout" ||
            method === "frappe.core.doctype.user.user.logout" ||
            /\.logout$/.test(String(method))
          ) {
            fireAndClear();
            return new Promise((resolve) => {
              setTimeout(() => resolve(origCall.apply(frappe, arguments)), 400);
            });
          }
          return origCall.apply(frappe, arguments);
        };
      }

      // (c) Catch clicks on any logout-shaped link. Broad selector covers most
      // Frappe versions: direct /logout anchors, data attributes, and
      // menu items whose text reads "Log out" / "Logout" / "Sign out".
      $(document).off("click.soundmgr-logout").on(
        "click.soundmgr-logout",
        'a[href="/logout"], a[href$="/logout"], a[href*="/logout"], [data-action="logout"], .logout',
        function (e) {
          const href = this.getAttribute && this.getAttribute("href");
          fireAndClear();
          if (href && href.indexOf("javascript:") !== 0) {
            e.preventDefault();
            setTimeout(() => {
              window.location.href = href;
            }, 400);
          }
          // If no href, let the default click handler run — our sound has
          // already fired and frappe.call or frappe.app.logout will handle
          // navigation with its own 400ms delay via wrappers (a)/(b).
        }
      );

      // Text-based fallback for menu items like "Log out" / "Sign out" that
      // have no href — re-scan on each click.
      $(document).off("click.soundmgr-logout-text").on(
        "click.soundmgr-logout-text",
        ".dropdown-item, .menu-item, a, button",
        function () {
          const t = ($(this).text() || "").trim().toLowerCase();
          if (t === "log out" || t === "logout" || t === "sign out") {
            fireAndClear();
          }
        }
      );
    }

    async loadFromServer() {
      const boot = window.frappe && frappe.boot && frappe.boot.user_sounds;
      if (boot) {
        this.enabled = boot.enabled !== 0;
        this.applyMapping(boot.mapping || {});
        return;
      }
      if (!window.frappe || !frappe.call) return;
      try {
        const r = await frappe.call({ method: "theme.api.get_user_sounds" });
        const m = (r && r.message) || {};
        this.enabled = m.enabled !== 0;
        this.applyMapping(m.mapping || {});
      } catch (_e) {
        /* keep defaults */
      }
    }
  }

  const mgr = new SoundManager();
  window.SoundManager = mgr;

  const init = async () => {
    mgr.patchPlaySound();
    mgr.wireRealtimeNotification();
    mgr.wireMissingFieldsSound();
    mgr.wireLogoutSound();
    await mgr.loadFromServer();
    // Login sound runs after mapping is applied so user's custom file (if any)
    // is already swapped onto the <audio id="sound-login"> element.
    mgr.wireLoginSound();
  };

  // Patch as soon as frappe.utils exists; otherwise wait for frappe.ready.
  if (window.frappe && frappe.utils && frappe.utils.play_sound) {
    init();
  } else if (window.frappe && typeof frappe.ready === "function") {
    frappe.ready(init);
  } else {
    document.addEventListener("DOMContentLoaded", init);
  }
})();
