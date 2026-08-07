import json
from pathlib import Path

from django.test import SimpleTestCase


from core.release_contract_assertions import assert_forward_compatible_release_identity

ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class LearningPlatformManagerGatewayContractTests(SimpleTestCase):
    def test_manager_gateway_uses_erp_identity_and_sidebar_entry(self):
        views = source("learning_platform/views.py")
        urls = source("learning_platform/urls.py")
        workflow = source("core/workflow_catalog.py")
        self.assertIn('@login_required(login_url="login")', views)
        self.assertIn("is_management_user(request.user)", views)
        self.assertIn('path("manage/", views.manager_dashboard, name="manager_dashboard")', urls)
        self.assertIn('"learning-platform"', workflow)
        self.assertIn('"learning_platform:manager_dashboard"', workflow)
        self.assertIn('{"label": "المنصة التعليمية", "items": ("learning-platform",)}', workflow)

    def test_platform_users_keep_independent_login_and_registration(self):
        urls = source("learning_platform/urls.py")
        session_auth = source("learning_platform/session_auth.py")
        forms = source("learning_platform/forms.py")
        self.assertIn('path("register/", views.register, name="register")', urls)
        self.assertIn('path("login/", views.login, name="login")', urls)
        self.assertIn('LEARNING_SESSION_KEY = "opal_learning_account_id"', session_auth)
        self.assertIn("مدير المنصة يدخل من حساب OPAL ERP", forms)

    def test_manager_shell_does_not_embed_erp_sidebar(self):
        template = source("templates/learning_platform/manager_dashboard.html")
        base = source("templates/learning_platform/base.html")
        self.assertIn("إدارة منصة أوبال التعليمية", template)
        self.assertIn("العودة إلى OPAL ERP", template)
        self.assertNotIn("includes/sidebar.html", template + base)
        self.assertNotIn("base/base.html", template + base)

    def test_r12_release_identity_is_coherent(self):
        assert_forward_compatible_release_identity(
            self,
            source,
            min_revision=15,
        )
