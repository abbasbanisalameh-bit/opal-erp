from datetime import date, timedelta

from django.test import TestCase

from attendance_v2.models import Attendance

from .models import Student
from .student360 import _build_attendance_profile


class StudentAttendanceProfileContractTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            student_number="LIFE-ATTENDANCE-001",
            full_name="طالب ملف الحضور",
            grade="الأول",
            section="أ",
        )

    def test_attendance_profile_preserves_counts_rate_and_order(self):
        today = date(2026, 7, 20)
        Attendance.objects.create(student=self.student, date=today, status="present")
        Attendance.objects.create(student=self.student, date=today - timedelta(days=1), status="present")
        Attendance.objects.create(student=self.student, date=today - timedelta(days=2), status="absent")
        Attendance.objects.create(student=self.student, date=today - timedelta(days=3), status="late")

        profile = _build_attendance_profile(self.student)

        self.assertEqual(profile["counts"], {"absent": 1, "late": 1, "present": 2})
        self.assertEqual(profile["total"], 4)
        self.assertEqual(profile["present_count"], 2)
        self.assertEqual(profile["absent_count"], 1)
        self.assertEqual(profile["late_count"], 1)
        self.assertEqual(profile["rate"], 50.0)
        self.assertEqual([row.date for row in profile["recent"]], [
            today,
            today - timedelta(days=1),
            today - timedelta(days=2),
            today - timedelta(days=3),
        ])

    def test_empty_attendance_profile_is_stable(self):
        profile = _build_attendance_profile(self.student)

        self.assertEqual(profile["counts"], {})
        self.assertEqual(profile["recent"], [])
        self.assertEqual(profile["total"], 0)
        self.assertEqual(profile["present_count"], 0)
        self.assertEqual(profile["absent_count"], 0)
        self.assertEqual(profile["late_count"], 0)
        self.assertEqual(profile["rate"], 0)
