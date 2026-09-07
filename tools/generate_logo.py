#!/usr/bin/env python3
"""Generate the Nexus Theme logo assets.

The mark is an "N" monogram drawn as one continuous rounded ribbon: a
left stem that turns into a hook at its foot, a diagonal, and a right
stem that turns into a hook at its head. The two hooks are 180-degree
rotations of each other, so the mark reads the same upside down.

It is built as a single stroked path with round caps and joins rather
than as filled outlines, which keeps the SVG tiny and means the weight
of the ribbon is one number (STROKE) instead of a hand-tuned contour.

The wordmark is set in Poppins and converted to outlines with fontTools,
so the lockups carry no font dependency at all. Poppins is licensed
under the SIL Open Font License; outlines embedded in a logo are a
permitted use.

    python3 tools/generate_logo.py

Fonts are looked for in FONT_DIRS. If none is found the mark and its
PNGs are still written, and only the wordmark lockups are skipped.
"""

from __future__ import annotations

import math
from pathlib import Path

# --- Mark geometry (512 x 512 canvas) -------------------------------

SIZE = 512
STROKE = 52.0  # ribbon weight
X_L, X_R = 127.0, 386.0  # stem centrelines
Y_TOP, Y_BOT = 124.0, 389.0  # stem extents

# The counter inside each loop measures 2*HOOK_R - STROKE, so the turn
# radius has to clear half the stroke by a real margin or the hook
# closes into a blob. Matching HOOK_R to STROKE leaves a counter exactly
# one stroke wide, which is the balance the reference mark strikes. The
# stems are then set wide enough apart that the hook tip still clears
# the diagonal — assert_clearances() checks that it does.
HOOK_R = 52.0
HOOK_TAIL = 20.0  # straight run after the turn

# --- Colour ---------------------------------------------------------

VIOLET = "#7C3AED"
BLUE = "#2B7FFF"
NAVY = "#101828"  # "NEXUS"
SLATE = "#2D3350"  # "THEME"
RULE = "#8B7FE8"  # the dashes flanking "THEME"

# --- Type -----------------------------------------------------------

FONT_DIRS = [Path("/tmp/fonts"), Path(__file__).resolve().parent / "fonts"]
FONT_BOLD = "Poppins-Bold.ttf"
FONT_MEDIUM = "Poppins-Medium.ttf"


def _find_font(name: str) -> Path | None:
	for d in FONT_DIRS:
		p = d / name
		if p.is_file():
			return p
	return None


# --- The ribbon -----------------------------------------------------


def mark_path() -> str:
	"""The monogram as one SVG path, traced foot-hook to head-hook.

	Both turns are semicircles. Travelling anticlockwise on screen for
	the foot and clockwise for the head is what makes the two hooks
	mirror through the centre.
	"""
	foot_tip_x = X_L + 2 * HOOK_R
	foot_y = Y_BOT - HOOK_R
	head_tip_x = X_R - 2 * HOOK_R
	head_y = Y_TOP + HOOK_R
	return (
		f"M{foot_tip_x:.2f} {foot_y - HOOK_TAIL:.2f}"
		f"L{foot_tip_x:.2f} {foot_y:.2f}"
		f"A{HOOK_R} {HOOK_R} 0 0 1 {X_L:.2f} {foot_y:.2f}"
		f"L{X_L:.2f} {Y_TOP:.2f}"
		f"L{X_R:.2f} {Y_BOT:.2f}"
		f"L{X_R:.2f} {head_y:.2f}"
		f"A{HOOK_R} {HOOK_R} 0 0 0 {head_tip_x:.2f} {head_y:.2f}"
		f"L{head_tip_x:.2f} {head_y + HOOK_TAIL:.2f}"
	)


def mark_bbox() -> tuple[float, float, float, float]:
	h = STROKE / 2
	return (X_L - h, Y_TOP - h, X_R + h, Y_BOT + h)


def _grad(gid: str) -> str:
	x0, y0, x1, y1 = mark_bbox()
	return (
		f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" '
		f'x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}">'
		f'<stop offset="0" stop-color="{VIOLET}"/>'
		f'<stop offset="1" stop-color="{BLUE}"/>'
		"</linearGradient>"
	)


def _stroked(paint: str, gid: str | None = None, indent: str = "  ") -> str:
	defs = f"{indent}<defs>{_grad(gid)}</defs>\n" if gid else ""
	return (
		f'{defs}{indent}<path d="{mark_path()}" fill="none" stroke="{paint}" '
		f'stroke-width="{STROKE:g}" stroke-linecap="round" stroke-linejoin="round"/>'
	)


def svg_mark() -> str:
	return (
		f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" '
		f'width="{SIZE}" height="{SIZE}" role="img" aria-label="Nexus Theme">\n'
		"  <title>Nexus Theme</title>\n"
		f"{_stroked('url(#nx)', 'nx')}\n"
		"</svg>\n"
	)


def svg_mono(colour: str = NAVY) -> str:
	return (
		f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" '
		f'width="{SIZE}" height="{SIZE}" role="img" aria-label="Nexus Theme">\n'
		"  <title>Nexus Theme</title>\n"
		f"{_stroked(colour)}\n"
		"</svg>\n"
	)


def svg_tile() -> str:
	inset = 0.74
	off = SIZE / 2 * (1 - inset)
	return (
		f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" '
		f'width="{SIZE}" height="{SIZE}" role="img" aria-label="Nexus Theme">\n'
		"  <title>Nexus Theme</title>\n"
		f"  <defs>{_grad('nxt')}</defs>\n"
		f'  <rect width="{SIZE}" height="{SIZE}" rx="112" fill="#0E1220"/>\n'
		f'  <g transform="translate({off:.2f} {off:.2f}) scale({inset})">\n'
		f"  {_stroked('url(#nxt)', indent='  ')}\n"
		"  </g>\n"
		"</svg>\n"
	)


# --- Text to outlines -----------------------------------------------


class Text:
	"""Glyph outlines for one string, laid out with fixed letterspacing."""

	def __init__(self, font_path: Path, text: str, size: float, tracking: float):
		from fontTools.pens.svgPathPen import SVGPathPen
		from fontTools.ttLib import TTFont

		font = TTFont(str(font_path))
		upem = font["head"].unitsPerEm
		cmap = font.getBestCmap()
		gs = font.getGlyphSet()
		hmtx = font["hmtx"]

		self.size = size
		self.scale = size / upem
		self.glyphs: list[tuple[str, float]] = []  # (path d, x offset)

		x = 0.0
		for ch in text:
			gname = cmap.get(ord(ch))
			if gname is None:
				x += size * 0.4 + tracking
				continue
			pen = SVGPathPen(gs)
			gs[gname].draw(pen)
			d = pen.getCommands()
			if d:
				self.glyphs.append((d, x))
			x += hmtx[gname][0] * self.scale + tracking
		self.width = x - tracking if text else 0.0

	def svg(self, x: float, baseline: float, fill: str, indent: str = "  ") -> str:
		"""Place the run with its left edge at x, sitting on `baseline`."""
		out = []
		for d, dx in self.glyphs:
			out.append(
				f'{indent}<path transform="translate({x + dx:.2f} {baseline:.2f}) '
				f'scale({self.scale:.6f} {-self.scale:.6f})" fill="{fill}" d="{d}"/>'
			)
		return "\n".join(out)


# --- Lockups --------------------------------------------------------

WORD_SIZE = 118.0
WORD_TRACK = 12.0
SUB_SIZE = 40.0
SUB_TRACK = 20.0


def svg_lockup() -> str | None:
	"""Stacked lockup: mark over NEXUS over a ruled THEME."""
	fb, fm = _find_font(FONT_BOLD), _find_font(FONT_MEDIUM)
	if not (fb and fm):
		return None

	word = Text(fb, "NEXUS", WORD_SIZE, WORD_TRACK)
	sub = Text(fm, "THEME", SUB_SIZE, SUB_TRACK)

	x0, y0, x1, y1 = mark_bbox()
	mark_w, mark_h = x1 - x0, y1 - y0

	gap_mark = 62.0
	gap_word = 42.0
	rule_gap, rule_len = 26.0, 54.0

	sub_span = sub.width + 2 * (rule_gap + rule_len)
	content_w = max(mark_w, word.width, sub_span)
	pad = 56.0
	W = content_w + 2 * pad
	cx = W / 2

	# Cap height carries the vertical rhythm; Poppins caps sit at ~0.70 em.
	cap_w = WORD_SIZE * 0.70
	cap_s = SUB_SIZE * 0.70
	y_mark = pad
	y_word_base = y_mark + mark_h + gap_mark + cap_w
	y_sub_base = y_word_base + gap_word + cap_s
	H = y_sub_base + pad

	sub_x = cx - sub.width / 2
	rule_y = y_sub_base - cap_s / 2
	scale_m = 1.0

	parts = [
		f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" '
		f'width="{W:.0f}" height="{H:.0f}" role="img" aria-label="Nexus Theme">',
		"  <title>Nexus Theme</title>",
		f"  <defs>{_grad('nxl')}</defs>",
		f'  <g transform="translate({cx - mark_w / 2 - x0:.2f} {y_mark - y0:.2f}) scale({scale_m})">',
		f"  {_stroked('url(#nxl)', indent='  ')}",
		"  </g>",
		word.svg(cx - word.width / 2, y_word_base, NAVY),
		sub.svg(sub_x, y_sub_base, SLATE),
		f'  <rect x="{sub_x - rule_gap - rule_len:.2f}" y="{rule_y - 1.6:.2f}" '
		f'width="{rule_len:.2f}" height="3.2" rx="1.6" fill="{RULE}"/>',
		f'  <rect x="{sub_x + sub.width + rule_gap:.2f}" y="{rule_y - 1.6:.2f}" '
		f'width="{rule_len:.2f}" height="3.2" rx="1.6" fill="{RULE}"/>',
		"</svg>",
	]
	return "\n".join(parts) + "\n"


def svg_wordmark() -> str | None:
	"""Horizontal lockup: mark beside NEXUS."""
	fb = _find_font(FONT_BOLD)
	if not fb:
		return None

	size = 96.0
	word = Text(fb, "NEXUS", size, 9.0)
	x0, y0, x1, y1 = mark_bbox()
	mark_w, mark_h = x1 - x0, y1 - y0

	target_h = 132.0
	s = target_h / mark_h
	gap = 40.0
	pad = 26.0
	W = pad * 2 + mark_w * s + gap + word.width
	H = pad * 2 + target_h
	cap = size * 0.70

	return (
		f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" '
		f'width="{W:.0f}" height="{H:.0f}" role="img" aria-label="Nexus Theme">\n'
		"  <title>Nexus Theme</title>\n"
		f"  <defs>{_grad('nxw')}</defs>\n"
		f'  <g transform="translate({pad - x0 * s:.2f} {pad - y0 * s:.2f}) scale({s:.5f})">\n'
		f"  {_stroked('url(#nxw)', indent='  ')}\n"
		"  </g>\n" + word.svg(pad + mark_w * s + gap, pad + target_h / 2 + cap / 2, NAVY) + "\n</svg>\n"
	)


# --- PNG ------------------------------------------------------------


def _mark_mask(size: int, ss: int, inset: float = 1.0):
	"""Anti-aliased alpha mask of the ribbon, drawn at ss x resolution."""
	from PIL import Image, ImageDraw

	big = size * ss
	k = big / SIZE * inset
	pad = big * (1 - inset) / 2

	def P(x: float, y: float) -> tuple[float, float]:
		return (x * k + pad, y * k + pad)

	m = Image.new("L", (big, big), 0)
	d = ImageDraw.Draw(m)
	w = STROKE * k

	foot_y, head_y = Y_BOT - HOOK_R, Y_TOP + HOOK_R
	foot_tip_x, head_tip_x = X_L + 2 * HOOK_R, X_R - 2 * HOOK_R

	for a, b in (
		((X_L, Y_TOP), (X_L, foot_y)),
		((X_L, Y_TOP), (X_R, Y_BOT)),
		((X_R, Y_BOT), (X_R, head_y)),
		((foot_tip_x, foot_y - HOOK_TAIL), (foot_tip_x, foot_y)),
		((head_tip_x, head_y), (head_tip_x, head_y + HOOK_TAIL)),
	):
		d.line([P(*a), P(*b)], fill=255, width=round(w))

	for cx, cy, s, e in (
		(X_L + HOOK_R, foot_y, 0, 180),
		(X_R - HOOK_R, head_y, 180, 360),
	):
		px, py = P(cx, cy)
		r = HOOK_R * k
		d.arc([px - r, py - r, px + r, py + r], s, e, fill=255, width=round(w))

	# Round every cap and joint.
	for x, y in (
		(X_L, Y_TOP),
		(X_L, foot_y),
		(X_R, Y_BOT),
		(X_R, head_y),
		(foot_tip_x, foot_y),
		(foot_tip_x, foot_y - HOOK_TAIL),
		(head_tip_x, head_y),
		(head_tip_x, head_y + HOOK_TAIL),
	):
		px, py = P(x, y)
		d.ellipse([px - w / 2, py - w / 2, px + w / 2, py + w / 2], fill=255)

	return m


def _gradient_rgb(big: int):
	"""Violet at top-left to blue at bottom-right, along the mark's bbox."""
	from PIL import Image

	v = tuple(int(VIOLET[i : i + 2], 16) for i in (1, 3, 5))
	b = tuple(int(BLUE[i : i + 2], 16) for i in (1, 3, 5))
	img = Image.new("RGB", (big, big))
	px = img.load()
	for y in range(big):
		for x in range(big):
			t = min(1.0, max(0.0, (x / big + y / big) / 2))
			px[x, y] = tuple(round(v[i] + (b[i] - v[i]) * t) for i in range(3))
	return img


def write_pngs(out_dir: Path) -> list[str]:
	try:
		from PIL import Image, ImageDraw
	except ImportError:
		return []

	written: list[str] = []
	ss = 4

	def render(size: int, tile: bool):
		big = size * ss
		mask = _mark_mask(size, ss, inset=0.74 if tile else 1.0)
		grad = _gradient_rgb(big)
		img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
		if tile:
			d = ImageDraw.Draw(img)
			d.rounded_rectangle([0, 0, big - 1, big - 1], radius=int(112 * big / SIZE), fill="#0E1220")
		img.paste(grad, (0, 0), mask)
		return img.resize((size, size), Image.LANCZOS)

	for size in (512, 256, 128, 64, 32, 16):
		p = out_dir / f"logo-{size}.png"
		render(size, tile=False).save(p)
		written.append(p.name)

	for size in (512, 192):
		p = out_dir / f"logo-tile-{size}.png"
		render(size, tile=True).save(p)
		written.append(p.name)

	ico = out_dir / "favicon.ico"
	render(64, tile=False).save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
	written.append(ico.name)
	return written


def main() -> None:
	out = Path(__file__).resolve().parent.parent / "logos"
	out.mkdir(parents=True, exist_ok=True)

	written = []
	for name, body in (
		("logo.svg", svg_mark()),
		("logo-mono.svg", svg_mono()),
		("logo-mono-light.svg", svg_mono("#FFFFFF")),
		("logo-tile.svg", svg_tile()),
	):
		(out / name).write_text(body, encoding="utf-8")
		written.append(name)

	for name, body in (
		("logo-lockup.svg", svg_lockup()),
		("logo-wordmark.svg", svg_wordmark()),
	):
		if body is None:
			print(f"  ! {name} skipped — Poppins not found in {FONT_DIRS}")
			continue
		(out / name).write_text(body, encoding="utf-8")
		written.append(name)

	written += write_pngs(out)

	print(f"wrote {len(written)} files to {out}:")
	for n in written:
		print(f"  {n}")


if __name__ == "__main__":
	main()
