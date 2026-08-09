from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class R35AndroidProductionAppContractTests(SimpleTestCase):
    def setUp(self):
        self.root = Path(settings.BASE_DIR)
        self.mobile = self.root / "mobile" / "opal_learning_app"

    def test_android_build_automation_exists(self):
        workflow = (self.mobile / "ci" / "opal-android-build.yml").read_text(encoding="utf-8")
        self.assertIn("flutter build apk --release", workflow)
        self.assertIn("flutter build appbundle --release", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertIn("OPAL_API_BASE_URL", workflow)


    def test_installer_command_can_materialize_hidden_github_workflow(self):
        command = (self.root / "core" / "management" / "commands" / "install_mobile_android_ci.py").read_text(encoding="utf-8")
        self.assertIn('mobile" / "opal_learning_app" / "ci" / "opal-android-build.yml', command)
        self.assertIn('".github" / "workflows" / "opal-android-build.yml', command)

    def test_mobile_source_uses_school_sso_secure_storage_and_in_app_video(self):
        source = (self.mobile / "lib" / "main.dart").read_text(encoding="utf-8")
        self.assertIn("auth/school-login/", source)
        self.assertIn("flutter_secure_storage", (self.mobile / "pubspec.yaml").read_text(encoding="utf-8"))
        self.assertIn("webview_flutter", (self.mobile / "pubspec.yaml").read_text(encoding="utf-8"))
        self.assertIn("LessonVideo", source)
        self.assertIn("subscription-cards/redeem/", source)

    def test_android_scaffold_script_enforces_https_and_internet_permission(self):
        script = (self.mobile / "tool" / "configure_android.py").read_text(encoding="utf-8")
        self.assertIn("android.permission.INTERNET", script)
        self.assertIn('android:usesCleartextTraffic="false"', script)

    def test_no_mobile_server_secret_is_embedded(self):
        source = (self.mobile / "lib" / "main.dart").read_text(encoding="utf-8").lower()
        forbidden = ["secret_key=", "payment_secret", "webhook_secret", "smtp_password"]
        for marker in forbidden:
            self.assertNotIn(marker, source)
