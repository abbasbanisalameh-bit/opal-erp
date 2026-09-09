from pathlib import Path
from django.test import SimpleTestCase


class R59DailyPrepareGatewayTests(SimpleTestCase):
    def test_single_explicit_daily_gateway(self):
        base = Path(__file__).resolve().parent
        urls = (base / "urls.py").read_text(encoding="utf-8")
        views = (base / "views.py").read_text(encoding="utf-8")
        services = (base / "services.py").read_text(encoding="utf-8")
        dashboard = (base / "templates" / "transport" / "dashboard.html").read_text(encoding="utf-8")
        assert urls.count('name="prepare-today"') == 1
        assert "def prepare_today(request):" in views
        assert "def prepare_today_operations" in services
        assert "تجهيز جولات اليوم" not in dashboard

    def test_dashboard_and_driver_do_not_reconcile_on_open(self):
        views = (Path(__file__).resolve().parent / "views.py").read_text(encoding="utf-8")
        assert 'reason="فتح مركز المواصلات"' not in views
        assert 'reason="فتح لوحة السائق"' not in views

    def test_gateway_delegates_to_single_synchronizer(self):
        services = (Path(__file__).resolve().parent / "services.py").read_text(encoding="utf-8")
        gateway = services.split("def prepare_today_operations", 1)[1].split("def synchronize_transport_operations", 1)[0]
        assert "synchronize_transport_operations(" in gateway
        assert "تجهيز جولات اليوم" in gateway
