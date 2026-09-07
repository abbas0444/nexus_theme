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

	function bindPasswordToggles(root) {
		var buttons = root.querySelectorAll("[data-nxlogin-toggle]");
		Array.prototype.forEach.call(buttons, function (button) {
			button.addEventListener("click", function () {
				var input = root.querySelector(button.getAttribute("data-nxlogin-toggle"));
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
		var email = root.querySelector("#login_email");
		var remember = root.querySelector("#nxlogin_remember");
		if (!email || !remember) return;

		var saved = read(USER_KEY);
		if (saved) {
			email.value = saved;
			remember.checked = true;
			var password = root.querySelector("#login_password");
			if (password) password.focus();
		}

		remember.addEventListener("change", function () {
			write(USER_KEY, remember.checked ? email.value.trim() || null : null);
		});

		var form = root.querySelector(".form-login");
		if (form) {
			form.addEventListener("submit", function () {
				write(USER_KEY, remember.checked ? email.value.trim() || null : null);
			});
		}
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
