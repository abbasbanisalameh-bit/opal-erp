from pathlib import Path

from django.test import SimpleTestCase


class R47CompleteTransportContractTests(SimpleTestCase):
    def test_prepare_today_gateway_remains_internal(self):
        urls = (Path(__file__).resolve().parent / "urls.py").read_text(encoding="utf-8")
        dashboard = (Path(__file__).resolve().parent / "templates" / "transport" / "dashboard.html").read_text(encoding="utf-8")
        assert 'name="prepare-today"' in urls
        assert "OPAL PREPARE TODAY GATEWAY START" not in dashboard
        assert "تجهيز جولات اليوم" not in dashboard

    def test_driver_fullscreen_uses_viewport_portal(self):
        text = (Path(__file__).resolve().parent / "templates" / "transport" / "driver" / "dashboard.html").read_text()
        assert "opal-map-viewport-layer" in text
        assert "document.body.appendChild(mapWrap)" in text

    def test_manager_fullscreen_uses_viewport_portal(self):
        text = (Path(__file__).resolve().parent / "templates" / "transport" / "tracking" / "manager.html").read_text()
        assert "opal-map-viewport-layer" in text
        assert "document.body.appendChild(mapWrap)" in text

    def test_parent_fullscreen_uses_viewport_portal(self):
        text = (Path(__file__).resolve().parent / "templates" / "transport" / "parent" / "dashboard.html").read_text()
        assert "opal-map-viewport-layer" in text
        assert "document.body.appendChild(mapWrap)" in text
