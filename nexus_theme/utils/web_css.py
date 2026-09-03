"""Build the CSS-variable block injected into login/website pages.

Kept free of any `frappe` import — like css_safety and contrast — because
this produces a string that is written verbatim into the <head> of every
public page. That is the highest-consequence output in the app, so it must
be unit-testable without a site.
"""

from nexus_theme.utils.css_safety import (
	COLOR_FIELDS,
	STYLE_FIELDS,
	is_safe_value,
)

# Theme Definition field -> the CSS custom property the stylesheets read.
# Mirrors VAR_MAP in public/js/theme_manager.js; test_website_theming.py
# asserts the two stay in step.
VAR_MAP = {
	"bg_primary": "--theme-bg-primary",
	"bg_surface": "--theme-bg-surface",
	"bg_input": "--theme-bg-input",
	"text_primary": "--theme-text-primary",
	"text_muted": "--theme-text-muted",
	"accent": "--theme-accent",
	"accent_hover": "--theme-accent-hover",
	"button_bg": "--theme-button-bg",
	"button_text": "--theme-button-text",
	"button_hover_bg": "--theme-button-hover-bg",
	"border": "--theme-border",
	"font_family": "--theme-font-family",
	"font_size_base": "--theme-font-size-base",
	"font_weight_base": "--theme-font-weight-base",
	"transition_duration": "--theme-transition-duration",
	"border_radius": "--theme-border-radius",
}


def theme_css_rules(theme: dict) -> str:
	"""Return the raw CSS for a theme, dropping anything unsafe.

	Raw rather than wrapped in <style> because this is injected through
	`colocated_css`, which Frappe already wraps. See website.py for why that
	is the only injection point that survives on the login page.

	Every value is re-checked here even though Theme Definition validated it
	on save. The guard is cheap, and unlike the Desk — where a bad value
	affects one logged-in user — this string reaches anonymous visitors on
	the login page. A value containing `}` would close the :root rule and
	turn everything after it into attacker-authored CSS.
	"""
	if not isinstance(theme, dict):
		return ""

	declarations = []
	for field, css_var in VAR_MAP.items():
		value = theme.get(field)
		if value in (None, ""):
			continue
		if field in COLOR_FIELDS or field in STYLE_FIELDS:
			if not is_safe_value(field, value):
				continue
		elif field == "font_weight_base":
			if not str(value).strip().isdigit():
				continue
		else:
			# An unknown field is never emitted: new tokens must be added to
			# a validator before they can reach the page.
			continue
		declarations.append(f"{css_var}:{value}")

	if not declarations:
		return ""

	# color-scheme makes the browser's own chrome — scrollbars, form control
	# defaults, autofill — match the theme. It is the CSS equivalent of the
	# polarity attribute the Desk sets on <html>.
	declarations.append("color-scheme:" + ("dark" if theme.get("is_dark") else "light"))
	return "/* nexus_theme-web-vars */:root{" + ";".join(declarations) + "}"


def theme_style_block(theme: dict) -> str:
	"""The same rules wrapped in a <style> tag, for any caller that needs to
	inject markup rather than CSS."""
	rules = theme_css_rules(theme)
	return f"<style id='nexus_theme-web-vars'>{rules}</style>" if rules else ""
