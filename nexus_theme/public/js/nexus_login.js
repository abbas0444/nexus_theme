(function () {
	"use strict";

	// ------------------------------------------------------------------
	// Small behaviours for the Nexus login page.
	//
	// Everything that actually signs a person in belongs to Frappe's own
	// templates/includes/login/login.js, which this page loads unchanged.
	// What is left is the show/hide password button and remembering the
	// username on this device, neither of which Frappe provides.
	// ------------------------------------------------------------------

	var USER_KEY = "nexus_theme:last_user";

	function read(key) {
		try {
			return window.localStorage ? localStorage.getItem(key) : null;
		} catch (_e) {
			return null;
		}
	}

	function write(key, value) {
		try {
			if (!window.localStorage) return;
			if (value === null) localStorage.removeItem(key);
			else localStorage.setItem(key, value);
		} catch (_e) {
			/* private windows and disabled storage are fine; the field just stays empty */
		}
	}

	// The email + password card is rendered twice when social login is on —
	// once in `.for-login`, once in `.for-email-login` — exactly as Frappe's
	// own login.html does it, and with the same ids, because Frappe's
	// login.js selects by those ids. Everything here therefore works per
	// form, scoped to the form or field it sits in, and never looks an id up
	// on the document: that always found the first card, so the second one
	// had a show-password button that toggled the wrong field and a
	// "remember me" box wired to another form.

	function visible(el) {
		return !!(el && el.offsetParent !== null);
	}

	// The password input the eye button belongs to: the one in its own field.
	// The attribute may still carry a selector; it is resolved inside the
	// containing form, never on the whole document.
	function inputForToggle(button) {
		var field = button.closest(".nxlogin-field");
		var input = field && field.querySelector("input");
		if (input) return input;
		var selector = button.getAttribute("data-nxlogin-toggle");
		var scope = button.closest("form") || document;
		return selector ? scope.querySelector(selector) : null;
	}

	function bindPasswordToggles(root) {
		var buttons = root.querySelectorAll("[data-nxlogin-toggle]");
		Array.prototype.forEach.call(buttons, function (button) {
			button.addEventListener("click", function () {
				var input = inputForToggle(button);
				if (!input) return;
				var hidden = input.getAttribute("type") === "password";
				input.setAttribute("type", hidden ? "text" : "password");
				button.classList.toggle("is-shown", hidden);
				input.focus();
			});
		});
	}

	// "Remember me" here means the username, not the session: Frappe decides
	// how long a session lasts in System Settings, and a checkbox that claimed
	// to change that would be telling the user something untrue.
	function bindRememberedUser(root) {
		var forms = root.querySelectorAll(".form-login");
		var saved = read(USER_KEY);
		var focused = false;

		Array.prototype.forEach.call(forms, function (form) {
			// Scoped lookups: with two cards there are two of each id, and
			// each form must find its own.
			var email = form.querySelector("#login_email");
			var remember = form.querySelector(".nxlogin-remember input[type='checkbox']");
			if (!email || !remember) return;

			if (saved) {
				email.value = saved;
				remember.checked = true;
				// Only the card on screen can take focus; the other is hidden.
				var password = form.querySelector("#login_password");
				if (!focused && password && visible(form)) {
					password.focus();
					focused = true;
				}
			}

			var store = function () {
				write(USER_KEY, remember.checked ? email.value.trim() || null : null);
			};
			remember.addEventListener("change", store);
			form.addEventListener("submit", store);
		});
	}

	// A logo that 404s or is not readable by an anonymous visitor would draw
	// the browser's broken-image icon in the corner of the sign-in screen.
	function hideBrokenImages(root) {
		var images = root.querySelectorAll(".nxlogin-brand-logo, .nxlogin-panel-image");
		Array.prototype.forEach.call(images, function (image) {
			image.addEventListener("error", function () {
				image.style.display = "none";
			});
			if (image.complete && image.naturalWidth === 0) image.style.display = "none";
		});
	}

	function start() {
		var root = document.querySelector("[data-nxlogin]");
		if (!root) return;
		bindPasswordToggles(root);
		bindRememberedUser(root);
		hideBrokenImages(root);
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", start);
	} else {
		start();
	}
})();
