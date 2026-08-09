from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class R34MobileBiometricContractTests(unittest.TestCase):
    def read(self, path):
        return (ROOT / path).read_text(encoding="utf-8")

    def test_school_mobile_sso_uses_erp_auth_and_scoped_learning_tokens(self):
        api = self.read("learning_platform/api.py")
        self.assertIn("def api_school_login", api)
        self.assertIn("authenticate(request=request, username=username, password=password)", api)
        self.assertIn("ensure_student_learning_account", api)
        self.assertIn("ensure_teacher_learning_account", api)
        self.assertIn("issue_api_token", api)
        self.assertNotIn("account.set_password(password)", api)

    def test_mobile_app_keeps_video_and_card_activation_inside_opal(self):
        source = self.read("mobile/opal_learning_app/lib/main.dart")
        self.assertIn("class LessonVideo", source)
        self.assertIn("WebViewWidget", source)
        self.assertIn("youtube-nocookie.com/embed", source)
        self.assertIn("subscription-cards/redeem/", source)
        self.assertIn("auth/school-login/", source)
        self.assertIn("flutter_secure_storage", self.read("mobile/opal_learning_app/pubspec.yaml"))

    def test_biometric_gateway_never_stores_fingerprint_templates(self):
        models = self.read("timetable/models.py")
        service = self.read("timetable/biometric_services.py")
        self.assertIn("class BiometricDevice", models)
        self.assertIn("class TeacherBiometricPunch", models)
        self.assertIn("class BiometricDailySummary", models)
        self.assertNotIn("fingerprint_template", models)
        self.assertNotIn("biometric_template", models)
        self.assertIn("punches are evidence", service)

    def test_biometric_evidence_requires_review_before_official_exception(self):
        service = self.read("timetable/biometric_services.py")
        self.assertIn("def rebuild_daily_summaries", service)
        self.assertIn("def apply_daily_summary", service)
        self.assertIn('review_status = "applied"', service)
        ingest_block = service.split("def ingest_punches", 1)[1].split("def expected_teacher_window", 1)[0]
        self.assertNotIn("TeacherAbsence.objects.update_or_create", ingest_block)

    def test_biometric_api_uses_per_device_secret(self):
        api = self.read("timetable/biometric_api.py")
        service = self.read("timetable/biometric_services.py")
        self.assertIn("X-OPAL-BIOMETRIC-TOKEN", api)
        self.assertIn("secrets.token_urlsafe", service)
        self.assertIn("hashlib.sha256", service)


if __name__ == "__main__":
    unittest.main()
