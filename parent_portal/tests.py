from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import School
from students.models import Student

from .models import Family, FamilyStudent


class ParentPortalPermissionsTests(TestCase):
    def setUp(self):
        self.parent = User.objects.create_user(username="parent_test", password="pass12345")
        self.staff = User.objects.create_user(username="staff_test", password="pass12345", is_staff=True)
        self.school = School.objects.create(name="Test School")
        self.family = Family.objects.create(user=self.parent, school=self.school, guardian_name="Parent")

    def test_parent_root_redirects_to_portal(self):
        self.client.force_login(self.parent)
        response = self.client.get("/")
        self.assertRedirects(response, reverse("parent_portal:dashboard"), fetch_redirect_response=False)

    def test_parent_cannot_open_admin_or_management_routes(self):
        self.client.force_login(self.parent)
        for path in ("/admin/", "/accounting/", "/students/", "/development/"):
            response = self.client.get(path)
            self.assertRedirects(response, reverse("parent_portal:dashboard"), fetch_redirect_response=False)

    def test_unlinked_user_cannot_open_parent_portal(self):
        other = User.objects.create_user(username="other", password="pass12345")
        self.client.force_login(other)
        response = self.client.get(reverse("parent_portal:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_staff_is_not_confined_to_parent_portal(self):
        self.client.force_login(self.staff)
        response = self.client.get("/admin/")
        self.assertNotEqual(response.status_code, 302)
