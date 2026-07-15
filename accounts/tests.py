from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import School
from teachers.models import Teacher


class ProfileAndImpersonationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="AdminPass123!",
        )
        self.teacher_user = User.objects.create_user(
            username="teacher1",
            password="TeacherPass123!",
        )
        school = School.objects.create(name="OPAL Test")
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_number="T-001",
            full_name="معلم الاختبار",
            school=school,
        )

    def test_superuser_can_impersonate_teacher_and_return(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("accounts:impersonate_user", args=[self.teacher_user.pk])
        )
        self.assertRedirects(response, reverse("teachers:portal_dashboard"))
        session = self.client.session
        self.assertEqual(int(session["_auth_user_id"]), self.teacher_user.pk)
        self.assertEqual(session["opal_impersonator_user_id"], self.admin.pk)

        response = self.client.post(reverse("accounts:stop_impersonation"))
        self.assertRedirects(response, reverse("dashboard:home"))
        session = self.client.session
        self.assertEqual(int(session["_auth_user_id"]), self.admin.pk)
        self.assertNotIn("opal_impersonator_user_id", session)

    def test_non_superuser_cannot_impersonate(self):
        self.client.force_login(self.teacher_user)
        response = self.client.post(
            reverse("accounts:impersonate_user", args=[self.admin.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_user_can_change_password_from_profile(self):
        self.client.force_login(self.teacher_user)
        response = self.client.post(
            reverse("accounts:my_profile"),
            {
                "action": "password",
                "password-old_password": "TeacherPass123!",
                "password-new_password1": "NewTeacherPass456!",
                "password-new_password2": "NewTeacherPass456!",
            },
        )
        self.assertRedirects(response, reverse("accounts:my_profile"))
        self.teacher_user.refresh_from_db()
        self.assertTrue(self.teacher_user.check_password("NewTeacherPass456!"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.teacher_user.pk)
