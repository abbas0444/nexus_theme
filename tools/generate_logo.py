#!/usr/bin/env python3
"""Generate the Nexus Theme logo assets.

The mark is a "nexus": a pointy-top hexagon with a flat-top hexagonal
aperture cut through its centre (rotated 30 degrees against the outer
ring). The ring between them divides into twelve facets — six pointing
out to a vertex, six pointing in to an aperture vertex — which cut the
shape like a gem.

Colour carries the product's one idea: a whole palette derived from a
single seed. Hue sweeps from the studio's own accent (#4f46e5) at the
top through to rose at the bottom, mirrored across the vertical axis so
the mark reads as balanced rather than as a pinwheel. Outward facets take
a lighter tone of their hue, inward facets a darker one.

Everything is generated from the geometry below, so the SVG and the PNG
renders cannot drift apart. Run:

    python3 tools/generate_logo.py
"""

from __future__ import annotations

import colorsys
import math
from pathlib import Path

# --- Geometry -------------------------------------------------------

SIZE = 512
CX = CY = SIZE / 2
R_OUTER = 200.0  # circumradius of the outer hexagon
R_INNER = 66.0  # circumradius of the aperture

# --- Colour ---------------------------------------------------------
# Hue sweep, in degrees, from the top of the mark to the bottom. 246 is
# the hue of #4f46e5, the accent Theme Studio already uses for itself.
HUE_TOP = 250.0
HUE_BOTTOM = 332.0

# Facets that point outward catch the light; the ones folding inward sit
# in shadow. Keeps the ring reading as a cut solid, not a colour wheel.
# The lit facets are held back in saturation and the shadowed ones sit
# deep rather than bright, which is what keeps the sweep from going neon.
SAT_OUT, LIGHT_OUT = 0.60, 0.685
SAT_IN, LIGHT_IN = 0.68, 0.445

INK = "#12101A"


def _pt(angle_deg: float, radius: float) -> tuple[float, float]:
	"""Polar to SVG coordinates (y grows downward)."""
	a = math.radians(angle_deg)
	return (CX + radius * math.cos(a), CY - radius * math.sin(a))


def _hue_at(clock_deg: float) -> float:
	"""Hue for a facet, by its angle clockwise from the top.

	Mirrored about the vertical axis: 30 degrees clockwise and 30
	degrees anticlockwise land on the same hue, so the mark is
	symmetrical.
	"""
	fold = clock_deg % 360.0
	if fold > 180.0:
		fold = 360.0 - fold
	return HUE_TOP + (HUE_BOTTOM - HUE_TOP) * (fold / 180.0)


def _hex(h_deg: float, light: float, sat: float) -> str:
	r, g, b = colorsys.hls_to_rgb((h_deg % 360.0) / 360.0, light, sat)
	return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def facets() -> list[tuple[list[tuple[float, float]], str]]:
	"""The twelve gem facets, each as (polygon points, fill).

	Outer hexagon vertices sit at 90, 150, ... (pointy top). The
	aperture is rotated 30 degrees, so its vertices sit at 60, 120, ...
	Each outer vertex is flanked by two aperture vertices and each outer
	edge spans one, which is what gives the twelve-facet cut.
	"""
	out: list[tuple[list[tuple[float, float]], str]] = []
	for k in range(6):
		theta = 90.0 + 60.0 * k  # outer vertex, maths convention
		clock = (90.0 - theta) % 360.0  # same point, clockwise from top

		v_out = _pt(theta, R_OUTER)
		w_prev = _pt(theta - 30.0, R_INNER)
		w_next = _pt(theta + 30.0, R_INNER)

		# Facet folding out to the vertex — catches the light.
		out.append(
			([w_next, v_out, w_prev], _hex(_hue_at(clock), LIGHT_OUT, SAT_OUT))
		)

		# Facet spanning the edge to the next vertex — folds inward.
		v_next = _pt(theta + 60.0, R_OUTER)
		w_mid = _pt(theta + 30.0, R_INNER)
		clock_edge = (90.0 - (theta + 30.0)) % 360.0
		out.append(
			([v_out, v_next, w_mid], _hex(_hue_at(clock_edge), LIGHT_IN, SAT_IN))
		)
	return out


def _poly(points: list[tuple[float, float]]) -> str:
	return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


# --- SVG ------------------------------------------------------------


def svg_mark() -> str:
	parts = [
		f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" '
		f'width="{SIZE}" height="{SIZE}" role="img" aria-label="Nexus Theme">',
		"  <title>Nexus Theme</title>",
	]
	for pts, fill in facets():
		parts.append(f'  <polygon points="{_poly(pts)}" fill="{fill}"/>')
	parts.append("</svg>")
	return "\n".join(parts) + "\n"


def svg_mono(colour: str = INK) -> str:
	"""Single-colour cut of the mark: outer hexagon, aperture knocked out."""
	outer = _poly([_pt(90.0 + 60.0 * k, R_OUTER) for k in range(6)])
	inner = _poly([_pt(60.0 + 60.0 * k, R_INNER) for k in range(6)])
	return (
		f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" '
		f'width="{SIZE}" height="{SIZE}" role="img" aria-label="Nexus Theme">\n'
		"  <title>Nexus Theme</title>\n"
		f'  <path fill="{colour}" fill-rule="evenodd" '
		f'd="M{outer.replace(" ", "L").replace(",", " ")}Z '
		f'M{inner.replace(" ", "L").replace(",", " ")}Z"/>\n'
		"</svg>\n"
	)


def svg_tile() -> str:
	"""App-icon lockup: the mark inset on a rounded, near-black tile."""
	pad = 0.78  # mark occupies 78% of the tile
	parts = [
		f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" '
		f'width="{SIZE}" height="{SIZE}" role="img" aria-label="Nexus Theme">',
		"  <title>Nexus Theme</title>",
		f'  <rect width="{SIZE}" height="{SIZE}" rx="112" fill="{INK}"/>',
		f'  <g transform="translate({CX:.2f} {CY:.2f}) scale({pad}) translate({-CX:.2f} {-CY:.2f})">',
	]
	for pts, fill in facets():
		parts.append(f'    <polygon points="{_poly(pts)}" fill="{fill}"/>')
	parts.extend(["  </g>", "</svg>"])
	return "\n".join(parts) + "\n"


def svg_wordmark() -> str:
	"""Horizontal lockup. Text uses a system stack, so it degrades safely."""
	h = 128.0
	scale = 96.0 / SIZE
	mark_w = SIZE * scale
	gap = 30.0
	total_w = mark_w + gap + 300.0
	parts = [
		f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w:.0f} {h:.0f}" '
		f'width="{total_w:.0f}" height="{h:.0f}" role="img" aria-label="Nexus Theme">',
		"  <title>Nexus Theme</title>",
		f'  <g transform="translate(0 {(h - SIZE * scale) / 2:.2f}) scale({scale:.5f})">',
	]
	for pts, fill in facets():
		parts.append(f'    <polygon points="{_poly(pts)}" fill="{fill}"/>')
	tx = mark_w + gap
	parts.extend(
		[
			"  </g>",
			f'  <text x="{tx:.1f}" y="{h / 2 + 3:.1f}" dominant-baseline="middle" '
			'font-family="Archivo, Avenir Next, Segoe UI, Helvetica Neue, Arial, sans-serif" '
			f'font-size="44" font-weight="700" letter-spacing="-1.2" fill="{INK}">Nexus</text>',
			f'  <text x="{tx + 137:.1f}" y="{h / 2 + 3:.1f}" dominant-baseline="middle" '
			'font-family="Archivo, Avenir Next, Segoe UI, Helvetica Neue, Arial, sans-serif" '
			f'font-size="44" font-weight="400" letter-spacing="-1.2" fill="{INK}">Theme</text>',
			"</svg>",
		]
	)
	return "\n".join(parts) + "\n"


# --- PNG ------------------------------------------------------------


def write_pngs(out_dir: Path) -> list[str]:
	"""Render PNGs from the same geometry, supersampled for clean edges."""
	try:
		from PIL import Image, ImageDraw
	except ImportError:
		return []

	written = []
	ss = 4  # supersample factor

	def render(size: int, tile: bool) -> "Image.Image":
		big = size * ss
		k = big / SIZE
		img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
		d = ImageDraw.Draw(img)
		if tile:
			d.rounded_rectangle(
				[0, 0, big - 1, big - 1], radius=int(112 * k), fill=INK
			)
			shrink, off = 0.78, CX * (1 - 0.78)
		else:
			shrink, off = 1.0, 0.0
		for pts, fill in facets():
			d.polygon(
				[((x * shrink + off) * k, (y * shrink + off) * k) for x, y in pts],
				fill=fill,
			)
		return img.resize((size, size), Image.LANCZOS)

	for size in (512, 256, 128, 64, 32, 16):
		p = out_dir / f"logo-{size}.png"
		render(size, tile=False).save(p)
		written.append(p.name)

	for size in (512, 192):
		p = out_dir / f"logo-tile-{size}.png"
		render(size, tile=True).save(p)
		written.append(p.name)

	# Multi-resolution favicon.
	ico = out_dir / "favicon.ico"
	render(64, tile=False).save(
		ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)]
	)
	written.append(ico.name)
	return written


def main() -> None:
	out = Path(__file__).resolve().parent.parent / "logos"
	out.mkdir(parents=True, exist_ok=True)

	(out / "logo.svg").write_text(svg_mark(), encoding="utf-8")
	(out / "logo-mono.svg").write_text(svg_mono(), encoding="utf-8")
	(out / "logo-mono-light.svg").write_text(svg_mono("#FFFFFF"), encoding="utf-8")
	(out / "logo-tile.svg").write_text(svg_tile(), encoding="utf-8")
	(out / "logo-wordmark.svg").write_text(svg_wordmark(), encoding="utf-8")

	names = [
		"logo.svg",
		"logo-mono.svg",
		"logo-mono-light.svg",
		"logo-tile.svg",
		"logo-wordmark.svg",
	] + write_pngs(out)

	print(f"wrote {len(names)} files to {out}:")
	for n in names:
		print(f"  {n}")

	print("\nfacet palette (clockwise from top):")
	for i, (_, fill) in enumerate(facets()):
		print(f"  facet {i:2d}  {fill}")


if __name__ == "__main__":
	main()
