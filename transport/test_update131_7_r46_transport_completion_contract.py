from pathlib import Path

from django.test import SimpleTestCase


class R46TransportCompletionContractTests(SimpleTestCase):

    def test_r46_transport_completion_contract(self):
        root = Path(__file__).resolve().parents[1]

        views = (
            root
            / "transport"
            / "views.py"
        ).read_text(encoding="utf-8")

        services = (
            root
            / "transport"
            / "services.py"
        ).read_text(encoding="utf-8")

        driver = (
            root
            / "transport"
            / "templates"
            / "transport"
            / "driver"
            / "dashboard.html"
        ).read_text(encoding="utf-8")

        manager = (
            root
            / "transport"
            / "templates"
            / "transport"
            / "tracking"
            / "manager.html"
        ).read_text(encoding="utf-8")

        parent = (
            root
            / "transport"
            / "templates"
            / "transport"
            / "parent"
            / "dashboard.html"
        ).read_text(encoding="utf-8")

        base = (
            root
            / "templates"
            / "base"
            / "base.html"
        ).read_text(encoding="utf-8")

        # السائق يرى الرحلة النشطة + رحلات اليوم المخططة
        assert "def driver_operational_trips(driver):" in services
        assert "models.Q(status=TransportTrip.ACTIVE)" in services
        assert "models.Q(service_date=today, status=TransportTrip.PLANNED)" in services

        # لا يوجد مسار انتحال للسائق
        assert driver.count("driver-impersonate-stop") == 0

        # زر إيقاف الانتحال موجود في الواجهة الأساسية فقط
        assert base.count("driver-impersonate-stop") == 1

        # وضع الخريطة fullscreen
        for text in (driver, manager, parent):
            assert "opal-map-fullscreen" in text
            assert "100vh" in text
            assert "wakeLock" in text
