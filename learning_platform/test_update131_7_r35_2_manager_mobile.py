import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import School

from .models import (
    LearningCourse,
    LearningManagerAPIToken,
    LearningSubject,
    LearningSubscriptionCard,
)


class R352ManagerMobileTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="opal-mobile-manager",
            password="Secret@123",
            is_staff=True,
            first_name="مدير",
            last_name="أوبال",
        )
        self.school = School.objects.create(name="مدرسة R35.2")

    def login_manager(self):
        response = self.client.post(
            reverse("learning_platform:api_school_login"),
            data=json.dumps(
                {
                    "username": "opal-mobile-manager",
                    "password": "Secret@123",
                    "device_name": "Android Manager Test",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["mode"], "manager")
        profile = data["profiles"][0]
        self.assertEqual(profile["account"]["role"], "manager")
        self.assertTrue(profile["token"].startswith("olm_"))
        return profile["token"]

    def test_erp_manager_uses_same_opal_credentials_without_learning_password(self):
        raw_token = self.login_manager()
        self.assertEqual(LearningManagerAPIToken.objects.count(), 1)
        response = self.client.get(
            reverse("learning_platform:api_me"),
            HTTP_AUTHORIZATION=f"Bearer {raw_token}",
        )
        self.assertEqual(response.status_code, 200)
        account = response.json()["data"]
        self.assertEqual(account["username"], self.manager.username)
        self.assertEqual(account["role"], "manager")

    def test_non_management_erp_account_does_not_receive_manager_mobile_token(self):
        User.objects.create_user(username="plain-r352", password="Secret@123")
        response = self.client.post(
            reverse("learning_platform:api_school_login"),
            data=json.dumps({"username": "plain-r352", "password": "Secret@123"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "unsupported_school_account")

    def test_manager_dashboard_requires_manager_token_and_returns_platform_stats(self):
        url = reverse("learning_platform:api_manager_dashboard")
        denied = self.client.get(url)
        self.assertEqual(denied.status_code, 401)
        raw_token = self.login_manager()
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {raw_token}")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("stats", data)
        self.assertIn("readiness", data)
        self.assertEqual(data["manager"]["role"], "manager")

    def test_manager_generates_unpredictable_cards_from_mobile_and_can_cancel_available_card(self):
        raw_token = self.login_manager()
        subject = LearningSubject.objects.create(name="رياضيات R35.2", slug="math-r352")
        response = self.client.post(
            reverse("learning_platform:api_manager_subscription_generate"),
            data=json.dumps(
                {
                    "quantity": 5,
                    "prefix": "OPAL",
                    "duration": LearningSubscriptionCard.Duration.MONTHLY,
                    "grants_all_subjects": False,
                    "subject_ids": [subject.pk],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {raw_token}",
        )
        self.assertEqual(response.status_code, 201)
        cards = response.json()["data"]
        self.assertEqual(len(cards), 5)
        codes = [item["code"] for item in cards]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(all(code.startswith("OPAL-") for code in codes))
        self.assertFalse(any(code.endswith(f"{index:06d}") for index, code in enumerate(codes, start=1)))

        card_id = cards[0]["id"]
        cancelled = self.client.post(
            reverse("learning_platform:api_manager_subscription_cancel", kwargs={"pk": card_id}),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {raw_token}",
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.json()["data"]["status"], LearningSubscriptionCard.Status.CANCELLED)

    def test_manager_can_change_school_wide_learning_access_from_mobile(self):
        raw_token = self.login_manager()
        url = reverse("learning_platform:api_manager_school_access")
        response = self.client.post(
            url,
            data=json.dumps(
                {
                    "action": "global",
                    "parent_default_enabled": True,
                    "teacher_sso_enabled": False,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {raw_token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["parent_default_enabled"])
        self.assertFalse(data["teacher_sso_enabled"])

    def test_manager_logout_revokes_manager_token(self):
        raw_token = self.login_manager()
        response = self.client.post(
            reverse("learning_platform:api_logout"),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {raw_token}",
        )
        self.assertEqual(response.status_code, 200)
        token = LearningManagerAPIToken.objects.get()
        self.assertIsNotNone(token.revoked_at)
        denied = self.client.get(
            reverse("learning_platform:api_manager_dashboard"),
            HTTP_AUTHORIZATION=f"Bearer {raw_token}",
        )
        self.assertEqual(denied.status_code, 401)
