from datetime import date

from django.test import TestCase
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
        module = Module.objects.create(name="اختبار الوحدة", key="test-module")
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
    def test_public_development_pages_redirect_or_load(self):
        urls = [
            "/development/",
            "/development/sprints/",
            "/development/backlog/",
            "/development/sprints/velocity/",
            "/development/notifications/",
        ]

        for url in urls:
            response = self.client.get(url)
            self.assertIn(response.status_code, [200, 302])
