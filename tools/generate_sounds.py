#!/usr/bin/env python3
"""Generate the bundled UI sound effects for Nexus Theme.

Every sound is synthesised from scratch using only the Python standard
library — no samples, no recordings, no third-party audio. Each resulting
file is therefore an original work owned by the app, free of any external
licence or attribution requirement.

Run from the app repository root:

    python3 tools/generate_sounds.py

Output: nexus_theme/public/sounds/<event>-<n>.wav
        12 events x 3 presets = 36 files. Preset 1 of each event is the
        "apt" default used by hooks.py.
"""

import math
import os
import random
import struct
import wave

SR = 44100  # sample rate (Hz)

OUT_DIR = os.path.join(
	os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
	"nexus_theme",
	"public",
	"sounds",
)

# Deterministic noise so re-running the script produces identical files.
random.seed(20260515)

# --- note frequencies (Hz) ------------------------------------------------
A3, C4, D4, E4, F4, G4 = 220.00, 261.63, 293.66, 329.63, 349.23, 392.00
A4, C5, D5, E5, F5, G5 = 440.00, 523.25, 587.33, 659.25, 698.46, 783.99
A5, C6, D6, E6, G6 = 880.00, 1046.50, 1174.66, 1318.51, 1568.00


# --- low-level synthesis --------------------------------------------------
def _adsr(samples, attack=0.006, release=0.055):
	"""Apply a short linear attack/release so edges never click. Both ramps
	are clamped to half the buffer so very short sounds stay intact."""
	n = len(samples)
	if n == 0:
		return samples
	a = min(max(1, int(SR * attack)), n // 2)
	r = min(max(1, int(SR * release)), n // 2)
	for i in range(a):
		samples[i] *= i / a
	for i in range(r):
		samples[n - 1 - i] *= i / r
	return samples


def _wave(timbre, phase):
	"""One sample of the requested timbre at the given phase (radians)."""
	if timbre == "sine":
		return math.sin(phase)
	if timbre == "bell":
		# fundamental plus quieter inharmonic partials -> metallic ring
		s = math.sin(phase) + 0.5 * math.sin(2.01 * phase) + 0.25 * math.sin(3.0 * phase)
		return s / 1.75
	if timbre == "square":
		# a few odd harmonics — softer than a raw square, no harsh aliasing
		s = sum(math.sin(k * phase) / k for k in (1, 3, 5, 7))
		return s * 0.62
	if timbre == "saw":
		s = sum(math.sin(k * phase) / k for k in range(1, 8))
		return s * 0.5
	return math.sin(phase)


def tone(freq, dur, vol=0.6, timbre="sine", decay=5.0):
	"""A single note with an exponential amplitude decay."""
	n = int(SR * dur)
	out = []
	for i in range(n):
		t = i / SR
		s = _wave(timbre, 2 * math.pi * freq * t)
		out.append(s * vol * math.exp(-decay * t))
	return _adsr(out)


def sweep(f0, f1, dur, vol=0.6, timbre="sine", decay=4.0):
	"""A note that glides linearly from f0 to f1."""
	n = int(SR * dur)
	out = []
	phase = 0.0
	for i in range(n):
		t = i / SR
		freq = f0 + (f1 - f0) * (i / n)
		phase += 2 * math.pi * freq / SR
		out.append(_wave(timbre, phase) * vol * math.exp(-decay * t))
	return _adsr(out)


def noise_click(dur=0.02, vol=0.45):
	"""A short low-passed noise burst — a crisp mechanical click."""
	n = int(SR * dur)
	out = []
	prev = 0.0
	for i in range(n):
		white = random.uniform(-1.0, 1.0)
		prev = prev * 0.5 + white * 0.5  # 1-pole low-pass softens the hiss
		out.append(prev * vol * math.exp(-60.0 * (i / SR)))
	return _adsr(out, attack=0.001, release=0.004)


def silence(dur):
	return [0.0] * int(SR * dur)


def seq(*parts):
	"""Concatenate sound segments end to end."""
	out = []
	for part in parts:
		out.extend(part)
	return out


def mix(*parts):
	"""Overlay sound segments, summing sample by sample."""
	length = max(len(p) for p in parts)
	out = [0.0] * length
	for part in parts:
		for i, value in enumerate(part):
			out[i] += value
	return out


def arp(freqs, note_dur=0.12, vol=0.6, timbre="sine", decay=6.0):
	"""A simple arpeggio — the notes played one after another."""
	return seq(*(tone(f, note_dur, vol, timbre, decay) for f in freqs))


def write_wav(path, samples):
	"""Peak-normalise to a consistent loudness and write a 16-bit mono WAV."""
	peak = max((abs(s) for s in samples), default=0.0) or 1.0
	gain = 0.85 / peak
	with wave.open(path, "w") as w:
		w.setnchannels(1)
		w.setsampwidth(2)
		w.setframerate(SR)
		frames = bytearray()
		for s in samples:
			clamped = max(-1.0, min(1.0, s * gain))
			frames += struct.pack("<h", int(clamped * 32767))
		w.writeframes(bytes(frames))


# --- per-event recipes ----------------------------------------------------
# Each event maps to exactly three (label, builder) presets. Preset 1 is the
# "apt" sound that best fits the action and serves as the registered default.
RECIPES = {
	"login": [
		("Welcome", lambda: arp([C5, E5, G5], 0.12, 0.6, "bell", 5.0)),
		("Unlock", lambda: seq(tone(G4, 0.10, 0.55, "sine", 8.0), tone(C6, 0.22, 0.6, "bell", 5.0))),
		("Bright", lambda: arp([C5, G5, C6], 0.12, 0.6, "sine", 6.0)),
	],
	"logout": [
		("Sign Off", lambda: arp([G5, E5, C5], 0.12, 0.55, "sine", 6.0)),
		("Soft", lambda: tone(A4, 0.32, 0.5, "sine", 4.0)),
		("Power Down", lambda: sweep(660, 220, 0.34, 0.55, "sine", 4.0)),
	],
	"save": [
		("Pop", lambda: seq(tone(E5, 0.06, 0.55, "sine", 12.0), tone(C6, 0.14, 0.6, "sine", 9.0))),
		("Ding", lambda: tone(C6, 0.22, 0.6, "bell", 7.0)),
		("Chirp", lambda: seq(tone(A5, 0.05, 0.5, "sine", 14.0), tone(E6, 0.10, 0.55, "sine", 12.0))),
	],
	"submit": [
		("Success", lambda: arp([C5, E5, G5, C6], 0.10, 0.6, "bell", 6.0)),
		("Confirm", lambda: seq(tone(E5, 0.10, 0.55, "sine", 9.0), tone(A5, 0.20, 0.6, "sine", 6.0))),
		("Bell", lambda: tone(G5, 0.34, 0.6, "bell", 4.0)),
	],
	"cancel": [
		("Soft", lambda: tone(D5, 0.16, 0.5, "sine", 8.0)),
		("Tick", lambda: tone(A3, 0.10, 0.5, "sine", 12.0)),
		("Down", lambda: seq(tone(D5, 0.09, 0.5, "sine", 10.0), tone(A4, 0.14, 0.5, "sine", 9.0))),
	],
	"delete": [
		("Drop", lambda: sweep(440, 150, 0.26, 0.6, "sine", 5.0)),
		("Thud", lambda: mix(tone(E4, 0.16, 0.6, "sine", 10.0), noise_click(0.04, 0.30))),
		("Swipe", lambda: sweep(600, 180, 0.20, 0.6, "saw", 7.0)),
	],
	"error": [
		("Buzz", lambda: tone(160, 0.26, 0.55, "square", 3.0)),
		("Alert", lambda: seq(tone(330, 0.12, 0.5, "square", 5.0), tone(247, 0.16, 0.5, "square", 4.0))),
		("Low", lambda: sweep(300, 170, 0.24, 0.5, "square", 4.0)),
	],
	"email": [
		("Ding", lambda: tone(D6, 0.22, 0.55, "bell", 6.0)),
		("Whoosh", lambda: sweep(420, 900, 0.22, 0.45, "sine", 5.0)),
		("Pop", lambda: tone(A5, 0.13, 0.5, "sine", 9.0)),
	],
	"alert": [
		(
			"Chirp",
			lambda: seq(tone(E6, 0.07, 0.5, "sine", 11.0), silence(0.04), tone(E6, 0.09, 0.5, "sine", 11.0)),
		),
		("Pulse", lambda: arp([A5, A5, A5], 0.07, 0.5, "sine", 12.0)),
		("Ring", lambda: tone(A5, 0.30, 0.55, "bell", 4.0)),
	],
	"click": [
		("Tick", lambda: tone(2000, 0.022, 0.4, "sine", 60.0)),
		("Tap", lambda: tone(1200, 0.034, 0.4, "sine", 45.0)),
		("Snap", lambda: noise_click(0.020, 0.45)),
	],
	"notification": [
		("Bell", lambda: tone(C6, 0.32, 0.55, "bell", 4.0)),
		("Ping", lambda: tone(E6, 0.18, 0.5, "bell", 6.0)),
		("Pop", lambda: tone(G5, 0.13, 0.5, "sine", 9.0)),
	],
	"missing_fields": [
		("Warn", lambda: seq(tone(D5, 0.10, 0.5, "sine", 8.0), tone(A4, 0.15, 0.5, "sine", 7.0))),
		("Nudge", lambda: tone(F4, 0.22, 0.45, "sine", 6.0)),
		("Buzz", lambda: tone(220, 0.16, 0.4, "square", 6.0)),
	],
}


def main():
	os.makedirs(OUT_DIR, exist_ok=True)
	count = 0
	for event, presets in RECIPES.items():
		for index, (label, builder) in enumerate(presets, start=1):
			path = os.path.join(OUT_DIR, f"{event}-{index}.wav")
			write_wav(path, builder())
			count += 1
			print(f"  {event}-{index}.wav  ({label})")
	print(f"\nGenerated {count} sound files in {OUT_DIR}")


if __name__ == "__main__":
	main()
