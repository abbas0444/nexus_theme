from theme.patches.v1_0.load_default_themes import execute as _execute


def execute():
	"""Re-run the idempotent theme seeder so newly-added default themes land
	in sites that already ran the v1_0 patch."""
	_execute()
