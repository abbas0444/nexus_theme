(function () {
  "use strict";

  // ------------------------------------------------------------------
  // Launcher pages for the two studios
  // ------------------------------------------------------------------
  // Theme Studio and Sound Studio are dialogs — openThemeSwitcher() and
  // openSoundStudio(). A Workspace can only link to a DocType, Report,
  // Dashboard, Page or URL, none of which can invoke a function, so a
  // dialog cannot be put on a workspace directly.
  //
  // Wrapping each one in a standard Frappe Page gives it a real route
  // (/app/theme-studio, /app/sound-studio) that a workspace shortcut,
  // the awesomebar and a bookmark can all reach. The page opens its
  // dialog on arrival and leaves a card behind to reopen it, so closing
  // the dialog doesn't dump the user on a blank screen.
  //
  // Both pages differ only in title, copy and which global they call,
  // hence this shared factory instead of two near-identical files.
  // ------------------------------------------------------------------

  const RETRY_MS = 150;
  const MAX_TRIES = 40; // ~6s; the openers ship in app_include_js bundles

  function callWhenReady(fnName, onFail) {
    let tries = 0;
    (function attempt() {
      if (typeof window[fnName] === "function") {
        window[fnName]();
        return;
      }
      if (++tries >= MAX_TRIES) {
        if (onFail) onFail();
        return;
      }
      setTimeout(attempt, RETRY_MS);
    })();
  }

  function render($container, opts) {
    const $card = $(`
      <div class="nxt-studio-launch">
        <div class="nxt-studio-icon">
          <img src="/assets/nexus_theme/images/logo.svg" alt="" width="56" height="56">
        </div>
        <h2 class="nxt-studio-title"></h2>
        <p class="nxt-studio-body"></p>
        <button class="btn btn-primary nxt-studio-open"></button>
        <p class="nxt-studio-hint">${frappe.utils.escape_html(
          __("Also available any time from the avatar menu, top right.")
        )}</p>
      </div>
    `);

    // Titles and copy go in via text() so translations can't inject markup.
    $card.find(".nxt-studio-title").text(__(opts.heading));
    $card.find(".nxt-studio-body").text(__(opts.body));
    $card.find(".nxt-studio-open").text(__(opts.cta));

    $card.find(".nxt-studio-open").on("click", function () {
      callWhenReady(opts.opener, function () {
        frappe.show_alert({
          message: __("{0} could not be opened. Try reloading the page.", [
            __(opts.heading),
          ]),
          indicator: "red",
        });
      });
    });

    $container.empty().append($card);
  }

  window.nexusStudioPage = function (wrapper, opts) {
    frappe.ui.make_app_page({
      parent: wrapper,
      title: __(opts.title),
      single_column: true,
    });

    render($(wrapper).find(".page-content"), opts);

    // Arriving on the page is itself the request to open the studio, so
    // fire it on every show. Closing the dialog leaves the card behind.
    $(wrapper).on("show", function () {
      callWhenReady(opts.opener);
    });
  };
})();
