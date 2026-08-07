from pathlib import Path
from django.test import SimpleTestCase


class Update66TopbarContractTests(SimpleTestCase):
    def test_topbar_keeps_official_search_notifications_and_profile(self):
        root = Path(__file__).resolve().parents[1]
        content = (root / "templates" / "includes" / "topbar.html").read_text(encoding="utf-8")
        self.assertIn('id="opal-global-operation-search"', content)
        self.assertIn('id="opal-notification-bell"', content)
        self.assertIn("accounts:my_profile", content)
        self.assertIn("opal-topbar-ribbon", content)

    def test_topbar_assets_use_current_release_cache_key(self):
        root = Path(__file__).resolve().parents[1]
        base = (root / "templates" / "base" / "base.html").read_text(encoding="utf-8")
        css = (root / "static" / "css" / "opal_dashboard_polish.css").read_text(encoding="utf-8")
        self.assertRegex(base, r"opal_dashboard_polish\.css' %\}\?v=[^\"\s]+")
        self.assertIn("OPAL Update 66", css)
