from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class LoginCsrfRecoveryTests(TestCase):
    def setUp(self):
        self.login_url = reverse("login")
        self.user = get_user_model().objects.create_user(
            username="csrf-admin",
            password="StrongPass123!",
            is_staff=True,
        )

    def test_login_response_is_not_cached_and_sets_csrf_cookie(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get(self.login_url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("csrftoken", response.cookies)

    def test_stale_login_token_redirects_to_fresh_login_form(self):
        client = Client(enforce_csrf_checks=True)
        client.get(self.login_url)
        stale_token = client.cookies["csrftoken"].value

        other_client = Client(enforce_csrf_checks=True)
        other_client.get(self.login_url)
        client.cookies["csrftoken"] = other_client.cookies["csrftoken"].value

        response = client.post(
            self.login_url,
            {
                "username": self.user.username,
                "password": "StrongPass123!",
                "csrfmiddlewaretoken": stale_token,
                "next": "/settings/",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("csrf_retry=1", response.url)
        self.assertIn("next=%2Fsettings%2F", response.url)
        self.assertIn("no-store", response["Cache-Control"])

        fresh_response = client.get(response.url)
        self.assertEqual(fresh_response.status_code, 200)
        self.assertContains(fresh_response, "تم تحديث جلسة الدخول لحمايتك")

    def test_non_login_csrf_failure_uses_friendly_opal_page(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("accounts:logout"))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "انتهت صلاحية الصفحة", status_code=403)
        self.assertNotContains(response, "Reason given for failure", status_code=403)
