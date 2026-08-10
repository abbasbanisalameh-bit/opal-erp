import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase

from core.models import SystemMobileAPIToken


ROOT = Path(__file__).resolve().parents[1]


class R37ErpMobileSourceContractTests(SimpleTestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_native_erp_flutter_app_and_official_school_brand_exist(self):
        pubspec = self.source("mobile/opal_erp_app/pubspec.yaml")
        main = self.source("mobile/opal_erp_app/lib/main.dart")
        self.assertIn("name: opal_erp_app", pubspec)
        self.assertIn("assets/opal-school-logo.png", pubspec)
        self.assertIn("نظام أوبال المدرسي", main)
        self.assertIn("https://opalschool2016.pythonanywhere.com/mobile/api/v1", main)
        self.assertIn("flutter_secure_storage", pubspec)

    def test_erp_mobile_api_is_role_scoped_and_read_only_in_r37(self):
        api = self.source("core/mobile_api.py")
        self.assertIn("ROLE_MODULES", api)
        self.assertIn('"accountant"', api)
        self.assertIn('"secretary"', api)
        self.assertIn('"teacher"', api)
        self.assertIn("def api_students", api)
        self.assertIn("def api_finance", api)
        self.assertIn("def api_timetable", api)
        self.assertNotIn("def api_delete_student", api)

    def test_separate_android_identity_and_ci_workflow(self):
        prepare = self.source("mobile/opal_erp_app/tool/prepare_android.sh")
        workflow = self.source("mobile/opal_erp_app/ci/opal-erp-android-build.yml")
        configure = self.source("mobile/opal_erp_app/tool/configure_android.py")
        self.assertIn("--project-name opal_erp_app", prepare)
        self.assertIn("OPAL ERP Android Build", workflow)
        self.assertIn("opal-erp-android-release", workflow)
        self.assertIn('android:label="نظام أوبال"', configure)


class R37ErpMobileAuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.User = get_user_model()

    def test_superuser_can_sign_in_and_token_is_hashed(self):
        user = self.User.objects.create_superuser(username="opal-mobile-admin", password="StrongPass!123", email="admin@example.com")
        response = self.client.post(
            "/mobile/api/v1/auth/login/",
            data=json.dumps({"username": user.username, "password": "StrongPass!123", "device_name": "Contract Test"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()["data"]
        raw = payload["token"]
        self.assertTrue(raw.startswith("oer_"))
        row = SystemMobileAPIToken.objects.get(user=user)
        self.assertNotEqual(row.token_hash, raw)
        me = self.client.get("/mobile/api/v1/me/", HTTP_AUTHORIZATION=f"Bearer {raw}")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["data"]["username"], user.username)
        self.assertIn("students", me.json()["data"]["modules"])

    def test_staff_account_can_sign_in_to_management_modules(self):
        user = self.User.objects.create_user(username="opal-mobile-staff", password="StrongPass!123", is_staff=True)
        response = self.client.post(
            "/mobile/api/v1/auth/login/",
            data=json.dumps({"username": user.username, "password": "StrongPass!123"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("students", response.json()["data"]["account"]["modules"])
        self.assertIn("finance", response.json()["data"]["account"]["modules"])

    def test_unprivileged_account_is_rejected(self):
        user = self.User.objects.create_user(username="ordinary-user", password="StrongPass!123")
        response = self.client.post(
            "/mobile/api/v1/auth/login/",
            data=json.dumps({"username": user.username, "password": "StrongPass!123"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "system_mobile_access_denied")
