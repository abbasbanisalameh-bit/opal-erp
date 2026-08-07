import re
from pathlib import Path

from django.test import SimpleTestCase


class Update111NotificationLayerContractTests(SimpleTestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]

    def test_topbar_stacking_context_is_above_sticky_module_navigation(self):
        topbar_css = (self.root / "static" / "css" / "opal_dashboard_polish.css").read_text(encoding="utf-8")
        main_css = (self.root / "static" / "css" / "opal_erp.css").read_text(encoding="utf-8")

        topbar_match = re.search(r"\.opal-topbar-shell\{[^}]*z-index:(\d+)", topbar_css)
        subnav_match = re.search(r"\.opal-module-subnav\s*\{[^}]*z-index:\s*(\d+)", main_css, re.S)

        self.assertIsNotNone(topbar_match)
        self.assertIsNotNone(subnav_match)
        self.assertGreater(int(topbar_match.group(1)), int(subnav_match.group(1)))
        self.assertIn("isolation:isolate", topbar_css)

    def test_notification_ancestors_do_not_clip_the_dropdown(self):
        css = (self.root / "static" / "css" / "opal_dashboard_polish.css").read_text(encoding="utf-8")
        for selector in (
            ".opal-topbar-shell",
            ".opal-topbar-main",
            ".opal-topbar-actions",
            ".opal-notification-dropdown",
        ):
            self.assertIn(selector, css)
        self.assertIn("overflow: visible !important", css)
        self.assertIn(".opal-notification-menu", css)
        self.assertIn("z-index: 4 !important", css)

    def test_base_template_busts_the_global_topbar_css_cache(self):
        base = (self.root / "templates" / "base" / "base.html").read_text(encoding="utf-8")
        self.assertRegex(base, r"opal_dashboard_polish\.css' %\}\?v=[^\"\s]+")
