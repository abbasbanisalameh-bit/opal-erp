from pathlib import Path

from django.test import SimpleTestCase


class R353FlutterManagerDashboardSyntaxHotfixContractTests(SimpleTestCase):
    def test_manager_stats_wrap_uses_closed_map_before_to_list(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "mobile" / "opal_learning_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        self.assertIn("children: cards\n                      .map(", source)
        self.assertIn(")\n                      .toList(),", source)

    def test_mobile_build_number_bumped(self):
        root = Path(__file__).resolve().parents[1]
        pubspec = (root / "mobile" / "opal_learning_app" / "pubspec.yaml").read_text(encoding="utf-8")
        self.assertIn("version: 1.2.1+38", pubspec)
