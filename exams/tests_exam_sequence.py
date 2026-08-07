from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from academics.models import Enrollment, Grade, Section, Subject
from core.academic_context import resolve_academic_context
from core.models import AcademicYear, Branch, School, Semester
from students.models import Student
from teachers.models import Teacher, TeacherAssignment

from .lifecycle import open_exam_cycle


class ExamSequenceGateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("manager", password="x")
        self.school = School.objects.create(name="OPAL Test")
        self.branch = Branch.objects.create(school=self.school, name="Main")
        self.year = AcademicYear.objects.create(
            school=self.school, name="2026/2027", start_date=date(2026, 8, 1),
            end_date=date(2027, 6, 30), is_current=True,
        )
        # AcademicYear is the one authoritative creator of its two terms.
        self.first = self.year.semesters.get(code="first")
        self.second = self.year.semesters.get(code="second")
        self.grade = Grade.objects.create(school=self.school, name="الأول", order=1)
        self.section = Section.objects.create(
            branch=self.branch, academic_year=self.year, grade=self.grade, name="أ"
        )
        self.subject = Subject.objects.create(academic_year=self.year, grade=self.grade, name="رياضيات")
        self.teacher = Teacher.objects.create(
            employee_number="T1", full_name="Teacher", school=self.school
        )
        TeacherAssignment.objects.create(
            teacher=self.teacher, academic_year=self.year, section=self.section, subject=self.subject
        )
        self.student = Student.objects.create(full_name="Student", student_number="S1")
        Enrollment.objects.create(
            student=self.student, academic_year=self.year, grade=self.grade,
            section=self.section, status="active"
        )

    def test_second_exam_is_blocked_until_first_is_published_with_all_marks(self):
        open_exam_cycle(academic_year=self.year, semester=self.first, exam_type="first", user=self.user)
        with self.assertRaises(ValidationError):
            open_exam_cycle(academic_year=self.year, semester=self.first, exam_type="second", user=self.user)

    def test_second_semester_is_not_activated_before_first_closure(self):
        context = resolve_academic_context(
            school=self.school, reference_date=date(2027, 2, 1), persist=False
        )
        self.assertIsNone(context.semester)
