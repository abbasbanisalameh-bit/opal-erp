from django.urls import reverse
from django.test import SimpleTestCase


class R50FamilyLocationCenterContractTests(SimpleTestCase):
    def test_family_location_routes_exist(self):
        self.assertEqual(reverse("transport:family-location-list"), "/transport/family-locations/")
        self.assertEqual(reverse("transport:family-location-edit", kwargs={"family_id": 1}), "/transport/family-locations/1/edit/")

    def test_family_location_editor_has_map_contract(self):
        template = open("transport/templates/transport/family_locations/form.html", encoding="utf-8").read()
        self.assertIn("family-location-map", template)
        self.assertIn("id_latitude", template)
        self.assertIn("id_longitude", template)
        self.assertIn("save_family_location", open("transport/views.py", encoding="utf-8").read())
