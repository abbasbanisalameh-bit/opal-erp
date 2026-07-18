from datetime import date, datetime, time

from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from academics.models import Grade, Section, Subject
from core.models import AcademicYear, Branch, School
from teachers.models import Teacher, TeacherAssignment

from .live_services import school_live_status
from .models import TimeSlot, TimetableEntry
from .services import build_smart_timetable


class SmartTimetableTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("smart-manager", password="x", is_staff=True)
        self.school = School.objects.create(name="مدرسة الجدول")
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي")
        self.year = AcademicYear.objects.create(
            school=self.school, name="2026/2027", start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30), is_current=True,
        )
        grade = Grade.objects.create(school=self.school, name="الأول")
        section = Section.objects.create(academic_year=self.year, branch=self.branch, grade=grade, name="أ")
        subject = Subject.objects.create(name="رياضيات", grade=grade)
        teacher = Teacher.objects.create(employee_number="SMART-T", full_name="معلم ذكي", school=self.school)
        self.assignment = TeacherAssignment.objects.create(
            teacher=teacher, academic_year=self.year, section=section, subject=subject, weekly_periods=3,
        )
        TimeSlot.objects.create(name="الحصة الأولى", start_time=time(8), end_time=time(8, 45), order=1)
        TimeSlot.objects.create(name="الحصة الثانية", start_time=time(9), end_time=time(9, 45), order=2)
        self.client.force_login(self.user)

    def test_builder_meets_weekly_periods_without_collisions(self):
        result = build_smart_timetable(academic_year=self.year, apply=True)
        self.assertEqual(len(result["created"]), 3)
        entries = TimetableEntry.objects.filter(generated_automatically=True)
        self.assertEqual(entries.count(), 3)
        self.assertEqual(entries.values("section", "day", "time_slot").distinct().count(), 3)
        self.assertEqual(entries.values("teacher", "day", "time_slot").distinct().count(), 3)

    def test_default_thursday_is_weekend(self):
        thursday = timezone.make_aware(datetime(2026, 7, 23, 9, 0))
        status = school_live_status(self.school, thursday, guardian=True)
        self.assertEqual(status["state"], "weekend")
        self.assertIn("اعتنوا بأبنائنا", status["message"])

    def test_smart_management_pages_render(self):
        for url in (
            reverse("timetable:dashboard"), reverse("timetable:smart_builder"),
            reverse("timetable:schedule_settings"), reverse("timetable:absence_center"),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
