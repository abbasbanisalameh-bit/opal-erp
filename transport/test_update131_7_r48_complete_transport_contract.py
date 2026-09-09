from pathlib import Path

from django.test import SimpleTestCase


class R48CompleteTransportContractTests(SimpleTestCase):
    def test_duplicate_impersonation_banner_is_guarded(self):
        text = (Path(__file__).resolve().parents[1] / "templates" / "base" / "base.html").read_text()
        assert "opal_is_impersonating and not opal_is_transport_driver_impersonating" in text
        assert text.count("driver-impersonate-stop") == 1

    def test_today_assignment_synchronizer_exists(self):
        text = (Path(__file__).resolve().parent / "services.py").read_text()
        assert "def synchronize_today_assignments" in text
        assert "transport_type__in=(\"go\", \"return\", \"both\")" in text

    def test_automatic_transport_synchronizer_is_present(self):
        text = (Path(__file__).resolve().parent / "services.py").read_text()
        assert "def synchronize_transport_operations" in text
        assert "def reconcile_transport_after_registration_change" in text

    def test_family_location_management_gateway_exists(self):
        text = (Path(__file__).resolve().parent / "urls.py").read_text()
        assert 'name="family-location-list"' in text
        assert 'name="request-missing-family-locations"' in text
