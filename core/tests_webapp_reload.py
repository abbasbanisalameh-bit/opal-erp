import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import AuditLog

from .webapp_reload import (
    WebAppReloadError,
    WebAppReloadResult,
    reload_pythonanywhere_webapp,
)


class PythonAnywhereReloadServiceTests(TestCase):
    @patch("core.webapp_reload._reload_by_wsgi_touch")
    def test_standard_domain_uses_wsgi_touch_without_api_token(self, touch):
        touch.return_value = WebAppReloadResult(True, "تم", "wsgi_touch", "opal.pythonanywhere.com")
        with patch.dict(os.environ, {}, clear=True):
            result = reload_pythonanywhere_webapp(request_host="opal.pythonanywhere.com")
        self.assertTrue(result.ok)
        touch.assert_called_once_with(domain="opal.pythonanywhere.com")

    def test_local_host_is_rejected_without_explicit_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(WebAppReloadError):
                reload_pythonanywhere_webapp(request_host="localhost")


class PythonAnywhereReloadViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            username="reload-admin", email="admin@example.com", password="pass-12345"
        )
        self.staff = user_model.objects.create_user(
            username="reload-staff", password="pass-12345", is_staff=True
        )

    @patch("core.webapp_reload.reload_pythonanywhere_webapp")
    def test_superuser_can_request_reload_and_action_is_audited(self, reload_service):
        reload_service.return_value = WebAppReloadResult(
            True,
            "تم إرسال أمر إعادة تحميل الموقع.",
            "wsgi_touch",
            "opal.pythonanywhere.com",
        )
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("core:updates_reload_webapp"),
            HTTP_HOST="opalschool2016.pythonanywhere.com",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertTrue(AuditLog.objects.filter(model_name="core.WebAppReload", action="update").exists())

    def test_staff_cannot_request_reload(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("core:updates_reload_webapp"))
        self.assertEqual(response.status_code, 302)

    def test_reload_endpoint_is_post_only(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("core:updates_reload_webapp"))
        self.assertEqual(response.status_code, 405)
