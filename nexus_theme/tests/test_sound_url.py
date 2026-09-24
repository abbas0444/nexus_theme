"""Unit tests for the rule a stored sound URL must satisfy.

Pure-logic tests — no database or Frappe site required.
"""

import unittest

from nexus_theme.utils.sound_url import SOUND_EXTENSIONS, is_sound_url


class TestSoundUrl(unittest.TestCase):
	def test_accepts_files_this_site_serves(self):
		for ok in (
			"/assets/nexus_theme/sounds/save-2.wav",
			"/files/chime.mp3",
			"/private/files/chime.opus",
			"  /files/chime.mp3  ",
			"/files/X.MP3",
		):
			self.assertTrue(is_sound_url(ok), ok)

	def test_accepts_the_names_frappe_keeps_on_upload(self):
		# Frappe does not strip these from an upload's name, so refusing
		# them here left an orphan File behind every such upload.
		for ok in (
			"/files/Ben's chime.mp3",
			"/files/bell & whistle.wav",
			"/files/Ding (1).weba",
			"/files/sub dir/nudge.flac",
			"/files/100%.mp3",
			"/files/ünïcode.aiff",
			"/private/files/old.aif",
		):
			self.assertTrue(is_sound_url(ok), ok)

	def test_every_listed_extension_passes(self):
		for ext in SOUND_EXTENSIONS:
			self.assertTrue(is_sound_url(f"/files/x.{ext}"), ext)

	def test_rejects_anything_that_is_not_a_local_sound_path(self):
		for bad in (
			"",
			None,
			"javascript:alert(1)",
			"data:audio/mp3;base64,AAAA",
			"https://example.com/x.mp3",
			"//example.com/x.mp3",
			"/etc/passwd",
			"/filesx/a.mp3",
			"/files/x.exe",
			"/files/a.mp3.exe",
			"/files/../../x.mp3",
			"/files/./x.mp3",
			"/files//x.mp3",
			"/assets/nexus_theme/sounds/save-1.wav?x=<script>",
			"/files/x.mp3#frag",
			'/files/a"b.mp3',
			"/files/a\\b.mp3",
			"/files/a<b>.mp3",
			"/files/a\nb.mp3",
		):
			self.assertFalse(is_sound_url(bad), repr(bad))
