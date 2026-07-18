from datetime import date, time

from django.core.exceptions import ValidationError
from django.test import TestCase

from students.models import Student

from .models import Attendance


class AttendanceModelTest(TestCase):
    def setUp(self):
        self.student = Student.objects.create(student_number="A-1", full_name="طالب حضور", grade="الأول")

    def test_departed_records_departure_time_automatically(self):
        record = Attendance.objects.create(student=self.student, date=date.today(), status="departed")
        self.assertIsNotNone(record.departure_time)

    def test_departure_must_be_after_arrival(self):
        record = Attendance(
            student=self.student, date=date.today(), status="present", arrival_time=time(9, 0), departure_time=time(8, 0)
        )
        with self.assertRaises(ValidationError):
            record.full_clean()

    def test_unique_daily_record(self):
        Attendance.objects.create(student=self.student, date=date.today(), status="present")
        duplicate = Attendance(student=self.student, date=date.today(), status="absent")
        with self.assertRaises(ValidationError):
            duplicate.full_clean()
