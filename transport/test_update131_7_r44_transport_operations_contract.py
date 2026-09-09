from pathlib import Path

from django.test import SimpleTestCase

from . import urls


class R44TransportOperationsContractTests(SimpleTestCase):
    def test_management_return_route_exists(self):
        self.assertTrue(
            any(
                getattr(pattern, "name", "") == "driver-impersonate-stop"
                for pattern in urls.urlpatterns
            )
        )

    def test_planning_groups_route_exists(self):
        self.assertTrue(
            any(
                getattr(pattern, "name", "") == "group-list"
                for pattern in urls.urlpatterns
            )
        )

    def test_tracking_templates_expose_mobile_map_controls(self):
        base = Path(__file__).resolve().parent / "templates" / "transport"
        for relative in (
            "driver/dashboard.html",
            "tracking/manager.html",
            "parent/dashboard.html",
        ):
            text = (base / relative).read_text(encoding="utf-8")
            self.assertIn("تكبير الخريطة", text)
            self.assertIn("opal-map-fullscreen", text)
            self.assertIn("wakeLock", text)
