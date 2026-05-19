"""Grant the new "Theme User" role to every existing Desk user.

The Theme Definition and per-user preference DocTypes previously granted
access through the "All" role, which also covers Website (portal) users.
They now use a dedicated "Theme User" role instead — this patch creates that
role on sites upgrading from an older release and assigns it to every System
user so their theme/sound self-service keeps working.
"""

from nexus_theme.install import provision_theme_user_role


def execute():
	provision_theme_user_role()
