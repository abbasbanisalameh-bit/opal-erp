from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from academics.models import Grade, Subject
from core.models import AcademicYear, School
from students.models import Student

from .models import Exam, StudentMark
from .services import student_academic_record


class ExamsWorkflowTest(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة")
        self.year = AcademicYear.objects.create(school=self.school, name="2026/2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 30))
        self.grade = Grade.objects.create(school=self.school, name="الأول", order=1)
        self.subject = Subject.objects.create(name="رياضيات", grade=self.grade)
        self.student = Student.objects.create(student_number="E-1", full_name="طالب امتحان", grade="الأول")
        self.exam = Exam.objects.create(
            name="الامتحان الأول", exam_type="monthly", academic_year=self.year, grade=self.grade, subject=self.subject,
            max_mark=Decimal("100"), pass_percentage=Decimal("60"), status="open"
        )

    def test_mark_validation_and_pass_result(self):
        mark = StudentMark(exam=self.exam, student=self.student, mark=Decimal("75"))
        mark.full_clean()
        mark.save()
        self.assertTrue(mark.is_passed)
        invalid = StudentMark(exam=self.exam, student=Student.objects.create(student_number="E-2", full_name="ثان", grade="الأول"), mark=Decimal("101"))
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_published_only_record_hides_draft_results(self):
        StudentMark.objects.create(exam=self.exam, student=self.student, mark=Decimal("90"))
        self.assertEqual(student_academic_record(self.student, published_only=True)["exam_count"], 0)
        self.exam.status = "published"
        self.exam.is_locked = True
        self.exam.save(update_fields=["status", "is_locked"])
        self.assertEqual(student_academic_record(self.student, published_only=True)["exam_count"], 1)

    def test_existing_mark_cannot_change_after_lock(self):
        mark = StudentMark.objects.create(exam=self.exam, student=self.student, mark=Decimal("80"))
        self.exam.status = "approved"
        self.exam.is_locked = True
        self.exam.save(update_fields=["status", "is_locked"])
        mark.mark = Decimal("85")
        with self.assertRaises(ValidationError):
            mark.full_clean()
