from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from academics.models import Enrollment, Grade, Section, Subject
from core.models import AcademicYear, Branch, School
from students.models import Student
from teachers.models import Teacher, TeacherAssignment

from .mark_entry_service import resolve_mark_entry_scope, save_exam_marks
from .models import Exam, StudentMark


class MarkEntryResilienceTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة مرونة العلامات", is_active=True)
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.year = AcademicYear.objects.create(school=self.school, name="2026/2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 30), is_current=True)
        self.grade = Grade.objects.create(school=self.school, name="السادس", order=6)
        self.section = Section.objects.create(academic_year=self.year, branch=self.branch, grade=self.grade, name="أ")
        self.subject = Subject.objects.create(grade=self.grade, name="علوم", code="S6")
        self.student = Student.objects.create(student_number="MR-1", full_name="طالب المرونة", grade=self.grade.name)
        Enrollment.objects.create(student=self.student, academic_year=self.year, grade=self.grade, section=self.section)
        self.user = User.objects.create_user("mark_resilience_teacher", is_staff=True)
        self.teacher = Teacher.objects.create(user=self.user, school=self.school, branch=self.branch, employee_number="MR-T", full_name="معلم المرونة")
        self.assignment = TeacherAssignment.objects.create(teacher=self.teacher, academic_year=self.year, section=self.section, subject=self.subject)
        self.exam = Exam.objects.create(exam_type="first", academic_year=self.year, semester=self.year.semesters.get(code="first"), grade=self.grade, subject=self.subject, status="open")

    def test_active_teacher_profile_precedes_legacy_staff_flag_and_arabic_digits_save(self):
        assignment, students = resolve_mark_entry_scope(self.user, self.exam, self.assignment.pk)
        self.assertEqual(assignment, self.assignment)
        saved, errors = save_exam_marks(
            exam=self.exam,
            students=students,
            payload={f"mark_{self.student.pk}": "١٨٫٥", f"notes_{self.student.pk}": "جيد"},
            user=self.user,
        )
        self.assertEqual(errors, [])
        self.assertEqual(saved, 1)
        self.assertEqual(StudentMark.objects.get().mark, 18.5)

    def test_expected_validation_error_is_returned_instead_of_http_500_exception(self):
        with patch.object(StudentMark, "save", side_effect=ValidationError("بيانات العلامة غير مكتملة")):
            saved, errors = save_exam_marks(
                exam=self.exam,
                students=[self.student],
                payload={f"mark_{self.student.pk}": "15"},
                user=self.user,
            )
        self.assertEqual(saved, 0)
        self.assertTrue(errors)
        self.assertIn("تعذر حفظ العلامات", errors[0])
