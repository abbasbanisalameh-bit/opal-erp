from datetime import date, datetime, time

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from academics.models import Grade, Section, Subject
from core.models import AcademicYear, Branch, School
from teachers.models import Teacher, TeacherAssignment

from .models import TimeSlot, TimetableEntry
from .workflow import build_horizontal_schedule_matrix


class TimetableValidationTest(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة")
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي")
        self.year = AcademicYear.objects.create(school=self.school, name="2026/2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 30))
        self.grade = Grade.objects.create(school=self.school, name="الأول", order=1)
        self.section_a = Section.objects.create(academic_year=self.year, branch=self.branch, grade=self.grade, name="أ")
        self.section_b = Section.objects.create(academic_year=self.year, branch=self.branch, grade=self.grade, name="ب")
        self.subject = Subject.objects.create(academic_year=self.year, name="رياضيات", grade=self.grade)
        self.teacher = Teacher.objects.create(employee_number="T-1", full_name="المعلم", school=self.school, branch=self.branch)
        TeacherAssignment.objects.create(teacher=self.teacher, academic_year=self.year, section=self.section_a, subject=self.subject)
        self.slot = TimeSlot.objects.create(name="الأولى", start_time=time(8, 0), end_time=time(8, 45), order=1)

    def test_time_slot_end_after_start(self):
        with self.assertRaises(ValidationError):
            TimeSlot.objects.create(name="خاطئة", start_time=time(9, 0), end_time=time(8, 0))

    def test_prevent_teacher_and_room_conflicts(self):
        TimetableEntry.objects.create(
            academic_year=self.year, section=self.section_a, subject=self.subject, teacher=self.teacher,
            day="sunday", time_slot=self.slot, room="101"
        )
        conflict = TimetableEntry(
            academic_year=self.year, section=self.section_b, subject=self.subject, teacher=self.teacher,
            day="sunday", time_slot=self.slot, room="101"
        )
        with self.assertRaises(ValidationError):
            conflict.full_clean()

    def test_assignment_mismatch_is_rejected(self):
        other = Teacher.objects.create(employee_number="T-2", full_name="معلم آخر", school=self.school)
        TeacherAssignment.objects.create(teacher=other, academic_year=self.year, section=self.section_b, subject=self.subject)
        entry = TimetableEntry(
            academic_year=self.year, section=self.section_a, subject=self.subject, teacher=other,
            day="monday", time_slot=self.slot,
        )
        with self.assertRaises(ValidationError):
            entry.full_clean()

    def test_horizontal_matrix_marks_today_and_the_current_lesson(self):
        entry = TimetableEntry.objects.create(
            academic_year=self.year,
            section=self.section_a,
            subject=self.subject,
            teacher=self.teacher,
            day="monday",
            time_slot=self.slot,
            room="101",
        )
        matrix = build_horizontal_schedule_matrix(
            [entry],
            now=timezone.make_aware(datetime(2026, 7, 27, 8, 20)),
        )

        monday = next(row for row in matrix["rows"] if row["code"] == "monday")
        self.assertTrue(monday["is_today"])
        self.assertTrue(monday["cells"][0]["is_current"])
        self.assertTrue(entry.is_current_lesson)
        self.assertTrue(matrix["has_current_lesson"])
