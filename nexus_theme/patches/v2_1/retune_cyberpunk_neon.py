"""Move Cyberpunk Neon to its quieter sidebar on sites that already have it.

2.1.0 shipped Cyberpunk Neon with a sidebar painted in its full magenta and
a wave pattern. On the Desk that block of neon fought the theme's cyan links,
and the login page — which followed the cyan accent — looked like a
different theme altogether. The theme now keeps the neon for accents: a
deep violet sidebar, a magenta active item that matches the buttons, cyan
links, and no pattern.

An ordinary migrate already rewrites bundled themes from the fixture after
the patches run; this is for `bench migrate --skip-fixtures`. It only moves
a row that still holds exactly what 2.1.0 shipped, so a System Manager who
retuned the sidebar keeps their own choice.
"""

import frappe

THEME = "cyberpunk-neon"
SHIPPED_IN_2_1_0 = {"sidebar_bg": "#a21caf", "sidebar_pattern": 1, "sidebar_active_bg": None}
NOW = {"sidebar_bg": "#1b1030", "sidebar_pattern": 0, "sidebar_active_bg": "#7e1f8f"}


def execute():
	if not frappe.db.exists("Theme Definition", THEME):
		return
	doc = frappe.get_doc("Theme Definition", THEME)
	if not doc.is_default:
		return
	for field, shipped in SHIPPED_IN_2_1_0.items():
		if (doc.get(field) or None) != shipped:
			return
	doc.update(NOW)
	try:
		doc.save(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="nexus_theme: could not retune Cyberpunk Neon")
