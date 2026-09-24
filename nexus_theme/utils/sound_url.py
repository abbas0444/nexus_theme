"""The one shape a stored sound URL may take.

A User Sound Mapping row's file becomes an `<audio src>` in that user's Desk
on every event, so an arbitrary URL is a stored outbound beacon to a
third-party host, and a scheme such as javascript: has no business anywhere
near a src attribute. Only a path this site serves passes: uploads land
under /files or /private/files, the bundled presets under /assets.

Frappe keeps an upload's name largely as given — apostrophes, ampersands,
brackets and non-ASCII letters all survive — so the path may hold any
character except the ones that could break out of an attribute or start a
query: control characters, double quotes, backslashes, angle brackets, "?"
and "#". Dot segments and empty segments are refused as well.

This module is intentionally free of any `frappe` import so it stays pure
and unit-testable; api._assert_sound_url does the throwing.
"""

import re

# What a browser will actually play through <audio>. Shared with the client's
# upload filter (sound_studio.js AUDIO_FILE_TYPES) — keep the two lists the same.
SOUND_EXTENSIONS = (
	"mp3",
	"wav",
	"ogg",
	"oga",
	"m4a",
	"aac",
	"flac",
	"webm",
	"weba",
	"opus",
	"aiff",
	"aif",
)

# \Z rather than $: $ also matches before a trailing newline.
SOUND_URL_RE = re.compile(
	r"^/(?:assets|files|private/files)/[^\x00-\x1f\x7f\"\\<>?#]+"
	r"\.(?:" + "|".join(SOUND_EXTENSIONS) + r")\Z",
	re.IGNORECASE,
)


def is_sound_url(url: str) -> bool:
	"""True when `url` is a sound file this site serves."""
	url = (url or "").strip()
	if not url or not SOUND_URL_RE.match(url):
		return False
	return "/../" not in url and "/./" not in url and "//" not in url
