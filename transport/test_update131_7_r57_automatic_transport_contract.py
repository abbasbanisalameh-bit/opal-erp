from pathlib import Path
from django.test import SimpleTestCase


class R57AutomaticTransportContractTests(SimpleTestCase):
    def test_daily_prepare_gateway_is_explicit_and_single(self):
        urls = (Path(__file__).resolve().parent / "urls.py").read_text(encoding="utf-8")
        dashboard = (Path(__file__).resolve().parent / "templates" / "transport" / "dashboard.html").read_text(encoding="utf-8")
        trips = (Path(__file__).resolve().parent / "templates" / "transport" / "trips" / "list.html").read_text(encoding="utf-8")
        assert 'name="prepare-today"' in urls
        assert "تجهيز جولات اليوم" not in dashboard
        assert "تجهيز جولات اليوم" not in trips
        assert "تحديث المحطات" not in trips

    def test_automatic_reconciliation_hooks_exist(self):
        services = (Path(__file__).resolve().parent / "services.py").read_text(encoding="utf-8")
        subscription = (Path(__file__).resolve().parent / "subscription_services.py").read_text(encoding="utf-8")
        assert "def synchronize_transport_operations" in services
        assert "def reconcile_transport_after_registration_change" in services
        assert "def reconcile_transport_after_family_location_change" in services
        assert "reconcile_transport_after_registration_change" in subscription

    def test_location_change_preserves_stable_group_membership(self):
        services = (Path(__file__).resolve().parent / "services.py").read_text(encoding="utf-8")
        location_fn = services.split("def reconcile_transport_after_family_location_change", 1)[1]
        assert "_ensure_registration_group" not in location_fn
        assert 'group_membership_changed\": False' in location_fn

    def test_operational_sync_is_not_triggered_by_dashboard_open(self):
        views = (Path(__file__).resolve().parent / "views.py").read_text(encoding="utf-8")
        assert 'synchronize_transport_operations(school=school, reason="فتح مركز المواصلات")' not in views
        assert 'synchronize_transport_operations(school=school, reason="فتح لوحة السائق")' not in views
        assert 'def prepare_today(request):' in views
        assert 'prepare_today_operations(school=school)' in views
