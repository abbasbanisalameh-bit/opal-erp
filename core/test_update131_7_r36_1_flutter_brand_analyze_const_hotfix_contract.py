from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]


class R361FlutterBrandAnalyzeConstHotfixContractTests(SimpleTestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_card_theme_is_const_for_flutter_analyze(self):
        main = self.source("mobile/opal_learning_app/lib/main.dart")
        self.assertIn("cardTheme: const CardThemeData(", main)
        self.assertNotIn("cardTheme: CardThemeData(", main)

    def test_r36_brand_identity_is_preserved(self):
        main = self.source("mobile/opal_learning_app/lib/main.dart")
        pubspec = self.source("mobile/opal_learning_app/pubspec.yaml")
        self.assertIn("assets/opal-learn-logo.png", pubspec)
        self.assertIn("version: 1.3.0+39", pubspec)
        self.assertIn("منصة أوبال التعليمية", main)
        self.assertIn("تعلّم. تقدّم. تألّق.", main)
