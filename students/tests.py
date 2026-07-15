from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import StudentForm
from .models import Student


class CanonicalStudentEntryTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("student_manager", password="pass", is_staff=True)
        self.student = Student.objects.create(
            student_number="CAN-001", full_name="طالب موحد", grade="الأول", section="أ"
        )

    def test_legacy_create_route_redirects_to_canonical_registration(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("students:student_create"))
        self.assertRedirects(response, reverse("admissions:direct_registration"), fetch_redirect_response=False)

    def test_personal_edit_cannot_change_academic_or_lifecycle_fields(self):
        fields = StudentForm(instance=self.student).fields
        for protected in ("student_number", "grade", "section", "status", "is_active", "ministry_student_id"):
            self.assertNotIn(protected, fields)

    def test_archive_route_is_lifecycle_redirect_not_direct_mutation(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("students:student_archive", args=[self.student.pk]))
        self.assertRedirects(
            response,
            reverse("academics:lifecycle_action", args=[self.student.pk]),
            fetch_redirect_response=False,
        )
        self.student.refresh_from_db()
        self.assertEqual(self.student.status, "active")

    def test_non_staff_cannot_open_student_update(self):
        user = User.objects.create_user("ordinary_user", password="pass")
        self.client.force_login(user)
        response = self.client.get(reverse("students:student_update", args=[self.student.pk]))
        self.assertEqual(response.status_code, 302)


class Student360MergeTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("student_360_manager", password="pass", is_staff=True)
        self.student = Student.objects.create(
            student_number="CAN-360", full_name="طالب 360", grade="الأول", section="أ", gender="male"
        )
        self.client.force_login(self.staff)

    def test_legacy_detail_redirects_to_360(self):
        response = self.client.get(reverse("students:student_detail", args=[self.student.pk]))
        self.assertRedirects(
            response,
            reverse("students:student_360", args=[self.student.pk]),
            fetch_redirect_response=False,
        )

    def test_student_list_has_one_unified_profile_action(self):
        response = self.client.get(reverse("students:student_list"))
        self.assertContains(response, "ملف 360°")
        self.assertNotContains(response, ">عرض<")

    def test_gender_is_rendered_from_canonical_choices(self):
        response = self.client.get(reverse("students:student_360", args=[self.student.pk]))
        self.assertContains(response, "ذكر")
