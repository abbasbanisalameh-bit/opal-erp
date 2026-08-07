from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from core.models import School
from documents.models import IssuedDocument

from .models import Teacher
from .payroll_services import reactivate_teacher, terminate_teacher


class TeacherTerminationUpdate123Tests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="OPAL Test School", official_name="OPAL Test School")
        self.account = User.objects.create_user(username="teacher123", password="test-pass")
        self.manager = User.objects.create_user(username="manager123", password="test-pass", is_staff=True)
        self.teacher = Teacher.objects.create(
            user=self.account,
            employee_number="T-123",
            full_name="Test Teacher",
            national_id="99000123",
            school=self.school,
            hire_date=timezone.localdate().replace(year=timezone.localdate().year - 1),
        )

    def test_termination_deactivates_account_and_issues_one_official_letter(self):
        teacher, document, summary = terminate_teacher(
            teacher=self.teacher,
            end_date=timezone.localdate(),
            reason="انتهاء العقد",
            user=self.manager,
        )
        teacher.refresh_from_db()
        self.account.refresh_from_db()
        self.assertFalse(teacher.is_active)
        self.assertFalse(self.account.is_active)
        self.assertEqual(document.teacher_id, teacher.pk)
        self.assertEqual(document.template.code, "teacher-termination")
        self.assertEqual(document.payload["kind"], "teacher_termination")
        self.assertIn("انتهاء العقد", document.content)
        self.assertEqual(IssuedDocument.objects.filter(teacher=teacher, template__code="teacher-termination").count(), 1)
        self.assertIn("assignments_deactivated", summary)
        with self.assertRaises(ValidationError):
            terminate_teacher(
                teacher=teacher,
                end_date=timezone.localdate(),
                reason="إجراء مكرر",
                user=self.manager,
            )

    def test_reactivation_does_not_delete_termination_document(self):
        teacher, document, _summary = terminate_teacher(
            teacher=self.teacher,
            end_date=timezone.localdate(),
            reason="انتهاء العقد",
            user=self.manager,
        )
        teacher, summary = reactivate_teacher(teacher=teacher)
        teacher.refresh_from_db()
        self.account.refresh_from_db()
        self.assertTrue(teacher.is_active)
        self.assertTrue(self.account.is_active)
        self.assertIsNone(teacher.end_date)
        self.assertEqual(teacher.end_reason, "")
        self.assertEqual(summary["assignments_reactivated"], 0)
        self.assertTrue(IssuedDocument.objects.filter(pk=document.pk).exists())
