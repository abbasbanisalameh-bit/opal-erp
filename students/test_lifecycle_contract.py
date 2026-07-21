from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .lifecycle import build_student_profile_context
from .models import Student
from .student360 import build_student_360_context


class StudentLifecycleContractTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("lifecycle_manager", password="pass", is_staff=True)
        self.student = Student.objects.create(
            student_number="LIFE-001",
            full_name="طالب دورة الحياة",
            grade="الأول",
            section="أ",
        )
        self.client.force_login(self.staff)

    def test_public_entry_point_delegates_to_existing_student360_builder(self):
        self.assertIs(build_student_profile_context.__globals__["build_student_360_context"], build_student_360_context)

    @patch("students.views.build_student_profile_context")
    def test_profile_and_print_views_use_same_lifecycle_entry_point(self, mocked_builder):
        mocked_builder.return_value = {"student": self.student}
        self.client.get(reverse("students:student_360", args=[self.student.pk]))
        self.client.get(reverse("students:student_360_print", args=[self.student.pk]))
        self.assertEqual(mocked_builder.call_count, 2)
