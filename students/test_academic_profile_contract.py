from datetime import date

from django.test import TestCase

from academics.models import Enrollment, Grade, Section
from core.models import AcademicYear, Branch, School

from .models import Student
from .student360 import _build_academic_profile


class StudentAcademicProfileContractTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة اختبار دورة الطالب")
        self.branch = Branch.objects.create(school=self.school, name="الفرع الرئيسي")
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 8, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        self.grade = Grade.objects.create(school=self.school, name="الأول")
        self.section = Section.objects.create(
            branch=self.branch,
            academic_year=self.year,
            grade=self.grade,
            name="أ",
        )
        self.student = Student.objects.create(
            student_number="LIFE-ACADEMIC-001",
            full_name="طالب الملف الأكاديمي",
            grade="الأول",
            section="أ",
        )

    def test_active_enrollment_is_selected_as_current(self):
        enrollment = Enrollment.objects.create(
            student=self.student,
            academic_year=self.year,
            grade=self.grade,
            section=self.section,
            status="active",
        )

        profile = _build_academic_profile(self.student)

        self.assertEqual(profile["enrollments"], [enrollment])
        self.assertEqual(profile["current_enrollment"], enrollment)

    def test_empty_profile_is_stable_when_student_has_no_enrollment(self):
        profile = _build_academic_profile(self.student)

        self.assertEqual(profile["enrollments"], [])
        self.assertIsNone(profile["current_enrollment"])
