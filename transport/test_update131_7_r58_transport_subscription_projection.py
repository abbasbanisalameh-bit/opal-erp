from pathlib import Path
from django.test import SimpleTestCase


class R58TransportSubscriptionProjectionTests(SimpleTestCase):
    def test_registration_projection_repair_exists(self):
        services = (Path(__file__).resolve().parent / "services.py").read_text(encoding="utf-8")
        assert "def _repair_registration_operational_projection" in services
        assert 'result["registration_projection"] = projection' in services

    def test_direction_is_derived_from_canonical_transport_type(self):
        services = (Path(__file__).resolve().parent / "services.py").read_text(encoding="utf-8")
        fn = services.split("def _repair_registration_operational_projection", 1)[1].split("def reconcile_transport_after_registration_change", 1)[0]
        assert 'registration.transport_type in ("go", "both")' in fn
        assert 'registration.transport_type in ("return", "both")' in fn
        assert 'assignment.morning_trip = morning' in fn
        assert 'assignment.return_trip = returning' in fn

    def test_explicit_daily_prepare_gateway_exists(self):
        services = (Path(__file__).resolve().parent / "services.py").read_text(encoding="utf-8")
        urls = (Path(__file__).resolve().parent / "urls.py").read_text(encoding="utf-8")
        dashboard = (Path(__file__).resolve().parent / "templates" / "transport" / "dashboard.html").read_text(encoding="utf-8")
        assert "def prepare_today_operations" in services
        assert 'name="prepare-today"' in urls
        assert "تجهيز جولات اليوم" not in dashboard
