import json
from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class R371NativeErpBaselineFixContractTests(SimpleTestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_release_identity_advances_after_r36_1(self):
        release = self.source("OPAL_RELEASE_NAME.txt").strip()
        manifest = json.loads(self.source("OPAL_UPDATE_MANIFEST.json"))
        self.assertEqual(release, "OPAL Update 131.7 R37.1 - Native ERP Android Baseline Fix")
        self.assertEqual(manifest["version_name"], release)
        self.assertEqual(manifest["baseline"], "OPAL Update 131.7 R36.1 - Flutter Brand Analyze Const Hotfix")
        self.assertGreaterEqual(manifest["package_revision"], 44)

    def test_r36_1_flutter_analyze_fix_is_preserved(self):
        main = self.source("mobile/opal_learning_app/lib/main.dart")
        self.assertIn("cardTheme: const CardThemeData(", main)

    def test_installer_restores_both_android_workflows(self):
        command = self.source("core/management/commands/install_erp_mobile_android_ci.py")
        self.assertIn('opal-erp-android-build.yml', command)
        self.assertIn('opal-android-build.yml', command)
        self.assertIn('mobile" / "opal_learning_app" / "ci"', command)
