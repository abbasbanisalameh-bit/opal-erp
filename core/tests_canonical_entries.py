from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from academics.models import Enrollment, Grade, Section, Subject
from admissions.models import GradeFee
from core.models import AcademicYear, Branch, School
from exams.models import Exam, StudentMark
from students.models import Student
from teachers.models import Teacher, TeacherAssignment


class CanonicalEntryRedirectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("manager", password="password", is_staff=True)
        self.client.force_login(self.user)
        self.school = School.objects.create(name="مدرسة المصادر", is_active=True)
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        self.grade = Grade.objects.create(school=self.school, name="الأول", order=1)
        GradeFee.objects.create(
            school=self.school,
            academic_year=self.year,
            grade=self.grade,
            tuition_fee=Decimal("1000"),
        )
        self.section = Section.objects.create(
            academic_year=self.year,
            branch=self.branch,
            grade=self.grade,
            name="أ",
        )
        self.student = Student.objects.create(
            student_number="CAN-ST-1",
            full_name="طالب المصدر الموحد",
            grade=self.grade.name,
        )

    def test_all_student_add_routes_redirect_to_direct_registration(self):
        canonical = reverse("admissions:direct_registration")
        for route in (
            reverse("students:student_create"),
            reverse("academics:student_create"),
            reverse("academics:student_admission"),
        ):
            response = self.client.get(route)
            self.assertRedirects(response, canonical, fetch_redirect_response=False)

    def test_legacy_student_profiles_redirect_to_student_360(self):
        canonical = reverse("students:student_360", args=[self.student.pk])
        for route in (
            reverse("students:student_detail", args=[self.student.pk]),
            reverse("academics:student_detail", args=[self.student.pk]),
            reverse("academics:student_academic_profile", args=[self.student.pk]),
        ):
            response = self.client.get(route)
            self.assertRedirects(response, canonical, fetch_redirect_response=False)

    def test_grade_and_section_edit_routes_open_canonical_structure(self):
        grade_response = self.client.get(reverse("academics:grade_update", args=[self.grade.pk]))
        self.assertEqual(grade_response.status_code, 302)
        self.assertIn(reverse("academics:academic_structure"), grade_response.url)
        self.assertIn(f"edit_grade={self.grade.pk}", grade_response.url)

        section_response = self.client.get(reverse("academics:section_update", args=[self.section.pk]))
        self.assertEqual(section_response.status_code, 302)
        self.assertIn(reverse("academics:academic_structure"), section_response.url)
        self.assertIn(f"edit_section={self.section.pk}", section_response.url)

    def test_mark_add_route_never_renders_single_mark_form(self):
        response = self.client.get(reverse("exams:mark_create"))
        self.assertRedirects(
            response,
            f"{reverse('exams:exam_list')}#marks-review",
            fetch_redirect_response=False,
        )

    def test_audit_command_is_read_only(self):
        before = (Student.objects.count(), Grade.objects.count(), Section.objects.count())
        call_command("audit_canonical_entries", verbosity=0)
        after = (Student.objects.count(), Grade.objects.count(), Section.objects.count())
        self.assertEqual(before, after)


class UnifiedMarkEntryTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة العلامات", is_active=True)
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        self.grade = Grade.objects.create(school=self.school, name="السابع", order=7)
        self.section_a = Section.objects.create(
            academic_year=self.year,
            branch=self.branch,
            grade=self.grade,
            name="أ",
        )
        self.section_b = Section.objects.create(
            academic_year=self.year,
            branch=self.branch,
            grade=self.grade,
            name="ب",
        )
        self.subject = Subject.objects.create(academic_year=self.year, name="رياضيات", code="M7", grade=self.grade)
        self.student_a = Student.objects.create(student_number="MARK-A", full_name="طالب أ", grade=self.grade.name)
        self.student_b = Student.objects.create(student_number="MARK-B", full_name="طالب ب", grade=self.grade.name)
        Enrollment.objects.create(
            student=self.student_a,
            academic_year=self.year,
            grade=self.grade,
            section=self.section_a,
        )
        Enrollment.objects.create(
            student=self.student_b,
            academic_year=self.year,
            grade=self.grade,
            section=self.section_b,
        )
        self.exam = Exam.objects.create(
            exam_type="first",
            academic_year=self.year,
            semester=self.year.semesters.get(code="first"),
            grade=self.grade,
            subject=self.subject,
            status="open",
        )
        self.teacher_user = User.objects.create_user("teacher", password="password")
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            school=self.school,
            branch=self.branch,
            employee_number="T-MARK-1",
            full_name="معلم العلامات",
        )
        self.assignment = TeacherAssignment.objects.create(
            teacher=self.teacher,
            academic_year=self.year,
            section=self.section_a,
            subject=self.subject,
        )

    def test_teacher_legacy_marks_url_redirects_to_canonical_exam_screen(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse("teachers:portal_marks", args=[self.assignment.pk]))
        expected = reverse("exams:exam_marks_bulk", args=[self.exam.pk])
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(expected))
        self.assertIn(f"assignment={self.assignment.pk}", response.url)

    def test_teacher_can_save_only_students_in_assigned_section(self):
        self.client.force_login(self.teacher_user)
        url = reverse("exams:exam_marks_bulk", args=[self.exam.pk]) + f"?assignment={self.assignment.pk}"
        response = self.client.post(
            url,
            {
                "assignment": self.assignment.pk,
                f"mark_{self.student_a.pk}": "18",
                f"notes_{self.student_a.pk}": "ممتاز",
                f"mark_{self.student_b.pk}": "19",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(StudentMark.objects.filter(exam=self.exam, student=self.student_a, mark=18).exists())
        self.assertFalse(StudentMark.objects.filter(exam=self.exam, student=self.student_b).exists())

    def test_staff_reviews_marks_but_cannot_enter_them(self):
        manager = User.objects.create_user("marks_manager", password="password", is_staff=True)
        self.client.force_login(manager)
        response = self.client.get(reverse("exams:exam_marks_bulk", args=[self.exam.pk]))
        self.assertEqual(response.status_code, 403)
