from datetime import date

import unittest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

if not settings.OPAL_ENABLE_DEVELOPMENT_CENTER:
    raise unittest.SkipTest("مركز التطوير مفصول عن إعدادات نظام المدرسة الإنتاجي")
from django.urls import reverse

from .models import (
    Module,
    Task,
    Sprint,
    SprintDailySnapshot,
    Notification,
)


class DevelopmentCenterModelsTest(TestCase):
    def test_create_module_task_and_sprint(self):
        module = Module.objects.create(name="اختبار الوحدة")
        sprint = Sprint.objects.create(
            title="Sprint Test",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 14),
        )

        task = Task.objects.create(
            title="مهمة اختبار",
            module=module,
            sprint=sprint,
            status="todo",
            progress=0,
        )

        self.assertEqual(str(task), "مهمة اختبار")
        self.assertEqual(task.sprint, sprint)
        self.assertEqual(sprint.tasks.count(), 1)

    def test_notification_creation(self):
        notification = Notification.objects.create(
            title="تنبيه اختبار",
            message="رسالة اختبار",
            level="warning",
        )

        self.assertFalse(notification.is_read)
        self.assertEqual(str(notification), "تنبيه اختبار")

    def test_sprint_snapshot_creation(self):
        sprint = Sprint.objects.create(title="Sprint Snapshot")

        snapshot = SprintDailySnapshot.objects.create(
            sprint=sprint,
            date=date(2026, 7, 1),
            total_tasks=10,
            remaining_tasks=6,
        )

        self.assertEqual(snapshot.total_tasks, 10)
        self.assertEqual(snapshot.remaining_tasks, 6)


class DevelopmentCenterPagesTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            username="development-superuser",
            email="development-superuser@example.com",
            password="test-pass-123",
        )
        self.staff = user_model.objects.create_user(
            username="development-staff",
            password="test-pass-123",
            is_staff=True,
        )

    def test_public_development_endpoints_redirect_to_login(self):
        for url in ("/development/", reverse("development_center:gantt_data")):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("login"), response.url)

    def test_staff_cannot_open_development_center_or_gantt_data(self):
        self.client.force_login(self.staff)
        for url in ("/development/", reverse("development_center:gantt_data")):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)

    def test_superuser_can_open_development_center_and_gantt_data(self):
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get("/development/").status_code, 200)
        self.assertEqual(self.client.get(reverse("development_center:gantt_data")).status_code, 200)
