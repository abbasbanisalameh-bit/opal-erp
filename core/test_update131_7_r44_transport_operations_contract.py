import json
from pathlib import Path

from django.test import SimpleTestCase


class Update1317R44TransportOperationsContractTests(SimpleTestCase):
    def test_release_identity_and_revision(self):
        root = Path(__file__).resolve().parent.parent
        manifest = json.loads((root / "OPAL_UPDATE_MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version_name"], "OPAL Update 131.7 R44 - Transport Operations Completion")
        self.assertEqual(manifest["package_revision"], 52)
        self.assertEqual(manifest["baseline"], "OPAL Update 131.7 R43 - Canonical Student Transport Subscriptions")

    def test_subscription_routes_are_registered(self):
        root = Path(__file__).resolve().parent.parent
        urls = (root / "transport" / "urls.py").read_text(encoding="utf-8")
        self.assertIn('name="subscription-list"', urls)
        self.assertIn('name="subscription-edit"', urls)

    def test_subscription_uses_canonical_registration(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "transport" / "subscription_services.py").read_text(encoding="utf-8")
        self.assertIn("StudentRegistration", source)
        self.assertIn("calculate_registration_totals", source)
        self.assertIn("TransportAssignment", source)
        self.assertIn("@transaction.atomic", source)
        self.assertIn('posted_paid > totals["net_total"]', source)

    def test_dashboard_links_to_subscription_center(self):
        root = Path(__file__).resolve().parent.parent
        template = (root / "transport" / "templates" / "transport" / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn("transport:subscription-list", template)
