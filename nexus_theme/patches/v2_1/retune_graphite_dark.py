"""Move Graphite Dark to a graphite sidebar on sites that already have it.

2.1.0 shipped Graphite Dark with a solid royal-blue sidebar: the largest
block of colour on the Desk, in a theme whose whole idea is quiet charcoal.
The sidebar is now graphite, flat, with a deep blue active item that ties
it to the blue buttons and links. The login panel follows the sidebar, so
it turns graphite with a blue glow too.

An ordinary migrate already rewrites bundled themes from the fixture after
the patches run; this is for `bench migrate --skip-fixtures`. It only moves
a row that still holds exactly what 2.1.0 shipped, so a System Manager who
retuned the sidebar keeps their own choice.
"""

import frappe

THEME = "graphite-dark"
SHIPPED_IN_2_1_0 = {"sidebar_bg": "#1d4ed8", "sidebar_active_bg": None}
NOW = {"sidebar_bg": "#111317", "sidebar_active_bg": "#1e3a6e", "sidebar_pattern": 0}


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
		frappe.log_error(title="nexus_theme: could not retune Graphite Dark")
