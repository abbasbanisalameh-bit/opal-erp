from datetime import date, datetime, time

from django.test import TestCase
from django.utils import timezone

from academics.models import Grade, Section, Subject
from core.models import AcademicYear, Branch, School
from teachers.models import Teacher, TeacherAssignment

from .live_services import management_live_status
from .models import ClassCoverage, SchoolDayEvent, TimeSlot, TimetableEntry, TeacherAbsence
from .workflow import build_horizontal_schedule_matrix


class LiveOperationsRepairTests(TestCase):
    monday = date(2026, 7, 27)

    def setUp(self):
        self.school = School.objects.create(name="مدرسة التشغيل الحي")
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_current=True,
        )
        self.grade = Grade.objects.create(school=self.school, name="السابع", order=7)
        self.section = Section.objects.create(
            academic_year=self.year,
            branch=self.branch,
            grade=self.grade,
            name="أ",
        )
        self.subject = Subject.objects.create(
            academic_year=self.year,
            grade=self.grade,
            name="الرياضيات",
            weekly_periods=2,
        )
        self.teacher = Teacher.objects.create(
            school=self.school,
            branch=self.branch,
            employee_number="LIVE-1",
            full_name="المعلم الأساسي",
        )
        self.free_teacher = Teacher.objects.create(
            school=self.school,
            branch=self.branch,
            employee_number="LIVE-2",
            full_name="المعلم المتفرغ",
        )
        self.substitute = Teacher.objects.create(
            school=self.school,
            branch=self.branch,
            employee_number="LIVE-3",
            full_name="المعلم البديل",
        )
        TeacherAssignment.objects.create(
            teacher=self.teacher,
            academic_year=self.year,
            section=self.section,
            subject=self.subject,
        )
        self.slot = TimeSlot.objects.create(
            name="الحصة الأولى",
            start_time=time(8, 0),
            end_time=time(8, 45),
            order=1,
        )
        self.monday_entry = TimetableEntry.objects.create(
            academic_year=self.year,
            section=self.section,
            subject=self.subject,
            teacher=self.teacher,
            day="monday",
            time_slot=self.slot,
        )
        self.tuesday_entry = TimetableEntry.objects.create(
            academic_year=self.year,
            section=self.section,
            subject=self.subject,
            teacher=self.teacher,
            day="tuesday",
            time_slot=self.slot,
        )

    def aware(self, hour, minute=0):
        return timezone.make_aware(datetime(2026, 7, 27, hour, minute))

    def test_daily_exception_does_not_leak_to_other_weekdays(self):
        TeacherAbsence.objects.create(
            teacher=self.teacher,
            date=self.monday,
            attendance_status="absent",
            absence_type="excused",
        )
        build_horizontal_schedule_matrix(
            [self.monday_entry, self.tuesday_entry],
            now=self.aware(8, 20),
            school=self.school,
        )
        self.assertEqual(self.monday_entry.teacher_state_code, "absent")
        self.assertEqual(self.tuesday_entry.teacher_state_code, "available")

    def test_management_status_lists_effective_busy_and_free_teachers(self):
        status = management_live_status(self.school, self.aware(8, 20))
        self.assertEqual(status["busy_teachers"], 1)
        self.assertEqual(status["busy_rows"][0]["teacher"], self.teacher)
        self.assertIn(self.free_teacher, status["free_teachers"])
        self.assertIn("الرياضيات", status["grade_rows"][0]["states"][0]["label"])

    def test_substitute_is_busy_instead_of_unavailable_original(self):
        TeacherAbsence.objects.create(
            teacher=self.teacher,
            date=self.monday,
            attendance_status="absent",
            absence_type="excused",
        )
        ClassCoverage.objects.create(
            entry=self.monday_entry,
            date=self.monday,
            substitute_teacher=self.substitute,
            status="assigned",
        )
        status = management_live_status(self.school, self.aware(8, 20))
        row = status["busy_rows"][0]
        self.assertEqual(row["teacher"], self.substitute)
        self.assertTrue(row["is_substitute"])
        self.assertEqual(row["original_teacher"], self.teacher)
        self.assertNotIn(self.teacher.pk, status["busy_teacher_ids"])

    def test_explicit_break_overrides_overlapping_class_and_busy_state(self):
        event = SchoolDayEvent.objects.create(
            school=self.school,
            name="الاستراحة الأولى",
            event_type="break",
            start_time=time(8, 15),
            end_time=time(8, 30),
            duration_minutes=15,
            placement_mode="fixed",
            days="monday",
        )
        event.sections.add(self.section)
        status = management_live_status(self.school, self.aware(8, 20))
        self.assertEqual(status["grade_rows"][0]["states"][0]["label"], "الاستراحة الأولى")
        self.assertEqual(status["busy_teachers"], 0)
        self.assertEqual(status["busy_rows"], [])

    def test_horizontal_grade_section_event_matrix_keeps_each_section_state(self):
        section_b = Section.objects.create(
            academic_year=self.year,
            branch=self.branch,
            grade=self.grade,
            name="ب",
        )
        event = SchoolDayEvent.objects.create(
            school=self.school,
            name="استراحة الشعبة ب",
            event_type="break",
            start_time=time(8, 15),
            end_time=time(8, 30),
            duration_minutes=15,
            placement_mode="fixed",
            days="monday",
        )
        event.sections.add(section_b)

        status = management_live_status(self.school, self.aware(8, 20))
        self.assertEqual(len(status["grade_columns"]), 1)
        column = status["grade_columns"][0]
        self.assertEqual(column["section_count"], 2)
        self.assertEqual([item["short_name"] for item in column["sections"]], ["أ", "ب"])
        self.assertEqual(column["sections"][0]["label"], "الرياضيات")
        self.assertEqual(column["sections"][1]["label"], "استراحة الشعبة ب")

    def test_before_first_event_is_not_reported_as_free_teacher_time(self):
        status = management_live_status(self.school, self.aware(7, 30))
        self.assertEqual(status["state"], "not_started")
        self.assertEqual(status["free_teachers_count"], 0)
        self.assertEqual(status["grade_columns"][0]["sections"][0]["label"], "لم يبدأ الدوام")

    def test_day_without_schedule_has_explicit_no_schedule_state(self):
        empty_school = School.objects.create(name="مدرسة بلا جدول")
        empty_branch = Branch.objects.create(school=empty_school, name="الرئيسي", is_main=True)
        empty_year = AcademicYear.objects.create(
            school=empty_school,
            name="2026/2027",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_current=True,
        )
        empty_grade = Grade.objects.create(school=empty_school, name="الأول", order=1)
        Section.objects.create(
            academic_year=empty_year,
            branch=empty_branch,
            grade=empty_grade,
            name="أ",
        )
        status = management_live_status(empty_school, self.aware(8, 20))
        self.assertEqual(status["state"], "no_schedule")
        self.assertEqual(status["free_teachers_count"], 0)
        self.assertEqual(status["grade_columns"][0]["sections"][0]["label"], "لا يوجد دوام مقرر اليوم")

    def test_finished_day_reports_outside_hours_and_no_free_busy_lists(self):
        status = management_live_status(self.school, self.aware(17, 0))
        self.assertEqual(status["state"], "finished")
        self.assertEqual(status["busy_teachers"], 0)
        self.assertEqual(status["free_teachers_count"], 0)
        self.assertEqual(status["grade_rows"][0]["states"][0]["label"], "خارج وقت الدوام")
