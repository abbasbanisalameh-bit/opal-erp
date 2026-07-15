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
        self.semester = self.year.semesters.get(code="first")
        self.exam = Exam.objects.create(
            name="الامتحان الأول", exam_type="first", academic_year=self.year, semester=self.semester,
            grade=self.grade, subject=self.subject, pass_percentage=Decimal("60"), status="open"
        )

    def test_mark_validation_and_pass_result(self):
        mark = StudentMark(exam=self.exam, student=self.student, mark=Decimal("15"))
        mark.full_clean()
        mark.save()
        self.assertTrue(mark.is_passed)
        invalid = StudentMark(exam=self.exam, student=Student.objects.create(student_number="E-2", full_name="ثان", grade="الأول"), mark=Decimal("21"))
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_published_only_record_hides_draft_results(self):
        StudentMark.objects.create(exam=self.exam, student=self.student, mark=Decimal("18"))
        self.assertEqual(student_academic_record(self.student, published_only=True)["exam_count"], 0)
        self.exam.status = "published"
        self.exam.is_locked = True
        self.exam.save(update_fields=["status", "is_locked"])
        self.assertEqual(student_academic_record(self.student, published_only=True)["exam_count"], 1)

    def test_existing_mark_cannot_change_after_lock(self):
        mark = StudentMark.objects.create(exam=self.exam, student=self.student, mark=Decimal("16"))
        self.exam.status = "approved"
        self.exam.is_locked = True
        self.exam.save(update_fields=["status", "is_locked"])
        mark.mark = Decimal("17")
        with self.assertRaises(ValidationError):
            mark.full_clean()


class OfficialAnnualReportCalculationTest(TestCase):
    def setUp(self):
        from academics.models import Enrollment

        self.school = School.objects.create(name="مدرسة الشهادة")
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
        )
        self.grade = Grade.objects.create(school=self.school, name="السابع", order=7)
        self.math = Subject.objects.create(name="رياضيات", grade=self.grade)
        self.arabic = Subject.objects.create(name="لغة عربية", grade=self.grade)
        self.student = Student.objects.create(student_number="REPORT-1", full_name="طالب الشهادة", grade="السابع")
        Enrollment.objects.create(student=self.student, academic_year=self.year, grade=self.grade, status="active")

    def _add_term(self, semester_code, math_marks, arabic_marks):
        semester = self.year.semesters.get(code=semester_code)
        for subject, values in ((self.math, math_marks), (self.arabic, arabic_marks)):
            for exam_type, mark in zip(("first", "second", "third", "final"), values):
                exam = Exam.objects.create(
                    exam_type=exam_type,
                    academic_year=self.year,
                    semester=semester,
                    grade=self.grade,
                    subject=subject,
                    status="open",
                )
                StudentMark.objects.create(exam=exam, student=self.student, mark=Decimal(str(mark)))

    def test_annual_average_is_average_of_the_two_semester_subject_averages(self):
        from .services import annual_report

        # First semester subject totals: 80 and 60 => term average 70.
        self._add_term("first", (15, 15, 15, 35), (10, 10, 10, 30))
        # Second semester subject totals: 100 and 80 => term average 90.
        self._add_term("second", (20, 20, 20, 40), (15, 15, 15, 35))

        report = annual_report(student=self.student, academic_year=self.year)
        self.assertEqual(report["first"]["average"], Decimal("70.00"))
        self.assertEqual(report["second"]["average"], Decimal("90.00"))
        self.assertEqual(report["annual_average"], Decimal("80.00"))
        self.assertTrue(report["complete"])
