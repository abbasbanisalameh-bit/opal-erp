from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from academics.models import Enrollment, Grade, Section
from core.models import AcademicYear, Branch, School
from students.models import Student

from .analytics import (
    build_school_attendance_period_snapshot,
    build_student_attendance_summaries,
)
from .models import Attendance, AttendanceRegister


class ExceptionOnlyAttendanceAnalyticsTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة تحليل الحضور")
        self.branch = Branch.objects.create(
            school=self.school,
            name="الرئيسي",
            is_main=True,
        )
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        self.grade = Grade.objects.create(
            school=self.school,
            name="الخامس",
            order=5,
        )
        self.section = Section.objects.create(
            academic_year=self.year,
            branch=self.branch,
            grade=self.grade,
            name="أ",
        )
        self.students = []
        for index in range(1, 4):
            student = Student.objects.create(
                student_number=f"ATT-{index}",
                full_name=f"طالب الحضور {index}",
                grade=self.grade.name,
                section=self.section.name,
            )
            Enrollment.objects.create(
                student=student,
                academic_year=self.year,
                grade=self.grade,
                section=self.section,
                status="active",
            )
            self.students.append(student)

    def _register(self, target_date):
        return AttendanceRegister.objects.create(
            academic_year=self.year,
            grade=self.grade,
            section=self.section,
            date=target_date,
            submitted_at=timezone.now(),
        )

    def test_school_snapshot_derives_presence_from_roster_and_exceptions(self):
        target_date = date(2026, 9, 10)
        self._register(target_date)
        Attendance.objects.create(
            student=self.students[0],
            academic_year=self.year,
            grade=self.grade,
            section=self.section,
            date=target_date,
            status="absent",
        )
        Attendance.objects.create(
            student=self.students[1],
            academic_year=self.year,
            grade=self.grade,
            section=self.section,
            date=target_date,
            status="departed",
        )

        day = build_school_attendance_period_snapshot(
            target_date,
            target_date,
            school=self.school,
        )["days"][target_date]

        self.assertEqual(day["roster_total"], 3)
        self.assertEqual(day["present"], 1)
        self.assertEqual(day["absent"], 1)
        self.assertEqual(day["departed"], 1)
        self.assertEqual(day["percent"], 33.3)
        self.assertTrue(day["has_data"])

    def test_student_summary_uses_submitted_register_days_as_denominator(self):
        first_day = date(2026, 9, 10)
        second_day = first_day + timedelta(days=1)
        self._register(first_day)
        self._register(second_day)
        Attendance.objects.create(
            student=self.students[0],
            academic_year=self.year,
            grade=self.grade,
            section=self.section,
            date=second_day,
            status="absent",
        )

        summary = build_student_attendance_summaries(
            [self.students[0]],
            start_date=first_day,
            end_date=second_day,
        )[self.students[0].pk]

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["present_count"], 1)
        self.assertEqual(summary["absent_count"], 1)
        self.assertEqual(summary["departed_count"], 0)
        self.assertEqual(summary["rate"], 50.0)

    def test_unsubmitted_register_does_not_create_false_presence(self):
        target_date = date(2026, 9, 12)
        AttendanceRegister.objects.create(
            academic_year=self.year,
            grade=self.grade,
            section=self.section,
            date=target_date,
        )

        day = build_school_attendance_period_snapshot(
            target_date,
            target_date,
            school=self.school,
        )["days"][target_date]

        self.assertFalse(day["has_data"])
        self.assertEqual(day["roster_total"], 0)
        self.assertEqual(day["percent"], 0)

    def test_historical_roster_uses_enrollment_dates_not_current_status_only(self):
        target_date = date(2026, 9, 15)
        enrollment = Enrollment.objects.get(student=self.students[0], academic_year=self.year)
        enrollment.status = "withdrawn"
        enrollment.ended_at = target_date + timedelta(days=1)
        enrollment.save()
        self._register(target_date)

        day = build_school_attendance_period_snapshot(
            target_date,
            target_date,
            school=self.school,
        )["days"][target_date]

        self.assertEqual(day["roster_total"], 3)
        self.assertEqual(day["present"], 3)

    def test_unregistered_exception_does_not_reduce_authoritative_roster(self):
        target_date = date(2026, 9, 16)
        self._register(target_date)
        Attendance.objects.create(
            student=self.students[0],
            academic_year=self.year,
            grade=self.grade,
            section=None,
            date=target_date,
            status="absent",
        )

        day = build_school_attendance_period_snapshot(
            target_date,
            target_date,
            school=self.school,
        )["days"][target_date]

        self.assertEqual(day["roster_total"], 3)
        self.assertEqual(day["present"], 3)
        self.assertEqual(day["absent"], 0)
        self.assertEqual(day["unregistered_absent"], 1)

    def test_legacy_exception_is_kept_in_student_history_without_fake_presence(self):
        target_date = date(2026, 9, 17)
        Attendance.objects.create(
            student=self.students[0],
            academic_year=self.year,
            grade=self.grade,
            section=self.section,
            date=target_date,
            status="absent",
        )

        summary = build_student_attendance_summaries(
            [self.students[0]],
            start_date=target_date,
            end_date=target_date,
        )[self.students[0].pk]

        self.assertEqual(summary["registered_days"], 0)
        self.assertEqual(summary["legacy_exception_days"], 1)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["present_count"], 0)
        self.assertEqual(summary["absent_count"], 1)
        self.assertEqual(summary["rate"], 0.0)
