"""WCAG contrast helpers used to validate theme definitions."""


def _normalize_hex(hex_color: str) -> str:
	h = (hex_color or "").strip().lstrip("#")
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
