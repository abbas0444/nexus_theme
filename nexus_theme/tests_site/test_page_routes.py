"""The app's Desk pages must stay reachable at their own addresses.

The Desk router resolves a route to a DocType before it looks for a Page, so
a Page whose name matches the slug of any DocType a System Manager can read
is silently replaced by that DocType's form or list. Frappe itself ships a
single DocType called "Permission Inspector", which is exactly how the app's
inspector page went missing at /app/permission-inspector. This test fails as
soon as any of the app's pages collides with a DocType, in Frappe or in any
other installed app.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

APP_PAGES = ("theme-studio", "sound-studio", "nexus-permission-inspector")


def desk_slug(name: str) -> str:
	"""The route slug the Desk router derives from a DocType name."""
	return name.lower().replace(" ", "-")


class TestPageRoutes(FrappeTestCase):
	def test_pages_exist_and_belong_to_the_app(self):
		for page in APP_PAGES:
			module = frappe.db.get_value("Page", page, "module")
			self.assertEqual(module, "Nexus Theme", f"Page {page} is missing or not owned by the app")

	def test_page_routes_do_not_collide_with_any_doctype(self):
		doctype_slugs = {desk_slug(name) for name in frappe.get_all("DocType", pluck="name")}
		for page in APP_PAGES:
			self.assertNotIn(
				page,
				doctype_slugs,
				f"/app/{page} would open a DocType instead of the app's page",
			)

	def test_pages_load_their_assets(self):
		from frappe.desk.desk_page import getpage

		for page in APP_PAGES:
			frappe.response.docs = []
			getpage(page)
			doc = frappe.response.docs[0]
			self.assertTrue(doc.get("script"), f"Page {page} has no script")
			if page == "nexus-permission-inspector":
				self.assertIn('frappe.templates["nexus_permission_inspector"]', doc["script"])
				self.assertTrue(doc.get("style"), "the inspector page has no stylesheet")
