"""Regression checks for the OPAL single-entry navigation update."""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from academics.models import Grade, Section, Subject
from accounts.models import Role, UserProfile
from core.models import AcademicYear, Branch, School
from parent_portal.models import Family, FamilyStudent
from students.models import Student
from teachers.models import Teacher, TeacherAssignment

from .workflow_catalog import get_operations_for_user, navigation_sections_for_user


class NavigationConsolidationTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة تنظيم المسارات", is_active=True)
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        self.grade = Grade.objects.create(school=self.school, name="السابع", order=7)
        self.section = Section.objects.create(
            academic_year=self.year,
            branch=self.branch,
            grade=self.grade,
            name="أ",
        )
        self.subject = Subject.objects.create(academic_year=self.year, grade=self.grade, name="الرياضيات", code="M-7")
        self.manager = User.objects.create_user("nav_manager", password="pass", is_staff=True)

    def test_sidebar_comes_from_available_operations_and_hides_system_only_actions(self):
        sections = navigation_sections_for_user(
            self.manager, route_name="documents:document_list", query_params={}
        )
        labels = [item["label"] for section in sections for item in section["items"]]
        self.assertIn("مركز الوثائق", labels)
        self.assertIn("منصة أوبال التعليمية", labels)
        self.assertNotIn("تحديثات النظام", labels)
        self.assertNotIn("مركز التطوير", labels)

        keys = {item["key"] for item in get_operations_for_user(self.manager)}
        self.assertNotIn("system-updates", keys)
        self.assertNotIn("development", keys)

    def test_system_administrator_has_one_update_entry_under_settings(self):
        administrator = User.objects.create_superuser(
            username="nav_root", email="nav_root@example.com", password="pass"
        )
        sections = navigation_sections_for_user(administrator, route_name="core:system_updates", query_params={})
        labels = [item["label"] for section in sections for item in section["items"]]
        self.assertIn("إعدادات النظام", labels)
        self.assertNotIn("تحديثات النظام", labels)
        self.assertIn("system-updates", {item["key"] for item in get_operations_for_user(administrator)})

    def test_parent_profile_uses_the_single_guardian_account_screen(self):
        parent = User.objects.create_user("nav_parent", password="pass")
        family = Family.objects.create(user=parent, school=self.school, guardian_name="ولي اختبار")
        student = Student.objects.create(
            student_number="NAV-P-1",
            full_name="طالب ولي الاختبار",
            grade=self.grade.name,
            section=self.section.name,
        )
        FamilyStudent.objects.create(family=family, student=student, relation="والد")

        self.client.force_login(parent)
        response = self.client.get(reverse("accounts:my_profile"))
        self.assertRedirects(response, reverse("parent_portal:account"), fetch_redirect_response=False)

        response = self.client.get(reverse("parent_portal:dashboard"))
        self.assertContains(response, "وثائق الأبناء")
        self.assertNotContains(response, "الملف الشامل")

    def test_teacher_students_legacy_route_redirects_to_workspace_scope(self):
        teacher_user = User.objects.create_user("nav_teacher", password="pass")
        teacher = Teacher.objects.create(
            user=teacher_user,
            employee_number="NAV-T-1",
            full_name="معلم التنظيم",
            school=self.school,
            branch=self.branch,
        )
        assignment = TeacherAssignment.objects.create(
            teacher=teacher,
            academic_year=self.year,
            section=self.section,
            subject=self.subject,
        )

        self.client.force_login(teacher_user)
        response = self.client.get(reverse("teachers:portal_students", args=[assignment.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("teachers:portal_workspace"), response.url)
        self.assertIn("mode=students", response.url)
        self.assertIn(f"assignment={assignment.pk}", response.url)

    def test_principal_role_reaches_the_same_management_gateways_as_staff(self):
        principal = User.objects.create_user("nav_principal", password="pass")
        role = Role.objects.create(code="principal", name="مدير المدرسة")
        UserProfile.objects.create(user=principal, school=self.school, role=role)

        self.client.force_login(principal)
        for route in ("dashboard:home", "attendance_v2:dashboard", "timetable:dashboard"):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200, route)

        response = self.client.get(reverse("academics:dashboard"))
        self.assertRedirects(
            response, reverse("academics:academic_structure"), fetch_redirect_response=False
        )
