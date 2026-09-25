"""The mini rail: whether a person keeps the Desk's left sidebar collapsed.

On Frappe 16 the app-wide sidebar can be folded down to an icon-only rail;
on Frappe 15 the per-page side section can be hidden. Either way the choice
is one yes/no per person, stored as `sidebar_collapsed` on their User Theme
Preference row so it follows them from browser to browser.

The value reaches the API from a form post, a JSON body or the console, so
it arrives as a bool, an int or a string. parse_collapsed() folds every
honest spelling into a bool and answers None for anything else, which the
API turns into a clear error rather than guessing.

Kept free of any `frappe` import so it stays pure and unit-testable;
api.set_sidebar_collapsed does the throwing.
"""

_TRUE = frozenset({"1", "true", "yes", "on", "collapsed"})
_FALSE = frozenset({"0", "false", "no", "off", "expanded", ""})


def parse_collapsed(value) -> bool | None:
	"""True / False for a recognisable yes or no, None for anything else.

	None itself reads as False: "not collapsed" is the sidebar's natural
	state and what an omitted argument should mean.
	"""
	if value is None:
		return False
	if isinstance(value, bool):
		return value
	if isinstance(value, int):
		return bool(value) if value in (0, 1) else None
	if isinstance(value, str):
		text = value.strip().lower()
		if text in _TRUE:
			return True
		if text in _FALSE:
			return False
	return None
