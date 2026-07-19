from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from academics.models import Grade, Subject
from core.models import AcademicYear, School

from .models import Curriculum


class CurriculumOperationalTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("curriculum_staff", password="pass", is_staff=True)
        self.plain = User.objects.create_user("curriculum_plain", password="pass")
        self.school = School.objects.create(name="مدرسة المناهج", is_active=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        self.grade = Grade.objects.create(school=self.school, name="الصف الثالث", order=3)
        self.subject = Subject.objects.create(grade=self.grade, name="العلوم", code="SCI-3")
        self.item = Curriculum.objects.create(
            academic_year=self.year,
            grade=self.grade,
            subject=self.subject,
            weekly_periods=4,
        )

    def test_curriculum_list_is_available_from_its_canonical_screen(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("curriculum:curriculum_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "الخطة الدراسية")
        self.assertContains(response, self.subject.name)

    def test_non_management_user_is_denied(self):
        self.client.force_login(self.plain)
        response = self.client.get(reverse("curriculum:curriculum_list"))
        self.assertRedirects(response, reverse("dashboard:home"), fetch_redirect_response=False)

    def test_closed_year_curriculum_cannot_be_changed_or_deleted(self):
        AcademicYear.objects.filter(pk=self.year.pk).update(is_closed=True, is_current=False)
        self.year.refresh_from_db()
        self.item.academic_year = self.year
        self.item.weekly_periods = 5
        with self.assertRaises(ValidationError):
            self.item.save()

        self.client.force_login(self.staff)
        response = self.client.post(reverse("curriculum:curriculum_delete", args=[self.item.pk]))
        self.assertRedirects(response, reverse("curriculum:curriculum_list"), fetch_redirect_response=False)
        self.assertTrue(Curriculum.objects.filter(pk=self.item.pk).exists())

    def test_create_and_update_routes_are_available_without_hiding_the_feature(self):
        self.client.force_login(self.staff)
        create_response = self.client.get(reverse("curriculum:curriculum_create"))
        update_response = self.client.get(reverse("curriculum:curriculum_update", args=[self.item.pk]))
        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(update_response.status_code, 200)
        self.assertContains(create_response, "إضافة خطة دراسية")
        self.assertContains(update_response, "تعديل خطة دراسية")
