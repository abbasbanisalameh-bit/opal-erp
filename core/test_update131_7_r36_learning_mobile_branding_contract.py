from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]


class R36LearningMobileBrandingContractTests(SimpleTestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_flutter_uses_approved_opal_learning_brand(self):
        main = self.source("mobile/opal_learning_app/lib/main.dart")
        pubspec = self.source("mobile/opal_learning_app/pubspec.yaml")
        self.assertIn("assets/opal-learn-logo.png", pubspec)
        self.assertIn("version: 1.3.0+39", pubspec)
        self.assertIn("Image.asset('assets/opal-learn-logo.png'", main)
        self.assertIn("منصة أوبال التعليمية", main)
        self.assertIn("تعلّم. تقدّم. تألّق.", main)

    def test_role_based_welcome_and_motivation_are_present(self):
        main = self.source("mobile/opal_learning_app/lib/main.dart")
        self.assertIn("class OpalWelcomeBanner", main)
        self.assertIn("String opalMotivation(String role)", main)
        self.assertIn("role == 'manager'", main)
        self.assertIn("role == 'teacher'", main)
        self.assertIn("role == 'learner'", main)

    def test_web_learning_platform_uses_same_approved_logo(self):
        base = self.source("templates/learning_platform/base.html")
        css = self.source("static/learning_platform/css/platform.css")
        self.assertIn("opal-learning-logo.png", base)
        self.assertIn("تعلّم · تقدّم · تألّق", base)
        self.assertIn("learning-brand-logo", css)
        self.assertIn("#0d5cb6", css.lower())
        self.assertIn("#0eb6b4", css.lower())

    def test_android_label_is_learning_platform_specific(self):
        configure = self.source("mobile/opal_learning_app/tool/configure_android.py")
        self.assertIn('android:label="منصة أوبال"', configure)
