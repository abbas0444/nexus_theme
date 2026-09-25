"""WCAG contrast helpers used to validate theme definitions."""


def _normalize_hex(hex_color: str) -> str:
	"""The six hex digits of a colour, from any form css_safety accepts.

	#rgba and #rrggbbaa are valid theme values, so the WCAG check has to
	read them too — a theme written with alpha channels used to skip the
	check altogether, because the ValueError raised here was taken to mean
	"not a colour". Alpha is dropped rather than refused: the formula is
	defined for opaque colours, and the contrast of the colour as if opaque
	is the most useful answer there is.
	"""
	h = (hex_color or "").strip().lstrip("#")
	if len(h) == 4:
		h = h[:3]
	elif len(h) == 8:
		h = h[:6]
	if len(h) == 3:
		h = "".join(c * 2 for c in h)
	if len(h) != 6:
		raise ValueError(f"invalid hex color: {hex_color!r}")
	return h


def _luminance(hex_color: str) -> float:
	h = _normalize_hex(hex_color)
	r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))

	def chan(c: float) -> float:
		return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

	r, g, b = chan(r), chan(g), chan(b)
	return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
	l1, l2 = _luminance(fg), _luminance(bg)
	lighter, darker = max(l1, l2), min(l1, l2)
	return (lighter + 0.05) / (darker + 0.05)


def passes_aa(fg: str, bg: str, large_text: bool = False) -> bool:
	return contrast_ratio(fg, bg) >= (3.0 if large_text else 4.5)


def mix_hex(color: str, other: str, weight: float) -> str:
	"""`weight` of `color` mixed with the rest of `other`, as #rrggbb.

	The sRGB mix CSS's color-mix(in srgb, …) performs, rounded the same way
	on both sides: theme_manager.js derives the sidebar's tint and gradient
	end with the identical formula, so the colours validated here are the
	colours the Desk paints.
	"""
	a = _normalize_hex(color)
	b = _normalize_hex(other)
	weight = min(1.0, max(0.0, float(weight)))
	out = []
	for i in (0, 2, 4):
		ca = int(a[i : i + 2], 16)
		cb = int(b[i : i + 2], 16)
		# Half rounds up, as Math.round does in the browser — Python's round()
		# goes to even and would drift one step from the client on a tie.
		out.append(int(ca * weight + cb * (1 - weight) + 0.5))
	return "#" + "".join(f"{c:02x}" for c in out)


def pick_text_color(backgrounds, preferred: str | None = None) -> str:
	"""A text colour that reads on every one of `backgrounds`.

	`preferred` (usually the theme's own text colour) wins whenever it clears
	AA on all of them, so a sidebar keeps the theme's voice where it can.
	Otherwise the answer is pure white or pure black, whichever has the
	better worst case — a gradient has two ends and the text sits on both.
	"""
	bgs = [b for b in (backgrounds or []) if b]
	if not bgs:
		return preferred or "#000000"

	def worst(fg: str) -> float:
		return min(contrast_ratio(fg, bg) for bg in bgs)

	if preferred:
		try:
			if worst(preferred) >= 4.5:
				return preferred
		except ValueError:
			pass
	return "#ffffff" if worst("#ffffff") >= worst("#000000") else "#000000"
