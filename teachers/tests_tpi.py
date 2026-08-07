from datetime import date, datetime, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from academics.models import Enrollment, Grade, Section, Subject
from attendance_v2.models import AttendanceRegister
from core.models import AcademicYear, Branch, School
from exams.models import Exam, StudentMark
from parent_portal.models import Family, FamilyStudent, TeacherMonthlyEvaluation
from students.models import Student
from timetable.models import TeacherAbsence

from .models import Homework, Teacher, TeacherAssignment
from .tpi import (
    _academic_metrics,
    _student_attendance_component,
    _work_attendance_component,
    calculate_open_snapshot,
    close_tpi_month,
    teacher_tpi_context,
)


class TeacherPerformanceIndexTests(TestCase):
    period = date(2026, 7, 1)

    def setUp(self):
        self.school = School.objects.create(name="مدرسة مؤشر الأداء")
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            midyear_break_start=date(2026, 6, 15),
            midyear_break_end=date(2026, 6, 20),
            is_current=True,
        )
        self.grade = Grade.objects.create(school=self.school, name="السابع", order=7)
        self.teacher_user = User.objects.create_user("tpi-teacher", password="x")
        self.teacher = Teacher.objects.create(
            school=self.school,
            branch=self.branch,
            user=self.teacher_user,
            employee_number="TPI-1",
            full_name="معلم المؤشر",
        )
        self.section = Section.objects.create(
            academic_year=self.year,
            branch=self.branch,
            grade=self.grade,
            name="أ",
            homeroom_teacher=self.teacher,
        )
        self.subject = Subject.objects.create(academic_year=self.year, grade=self.grade, name="رياضيات", weekly_periods=5)
        self.assignment = TeacherAssignment.objects.create(
            teacher=self.teacher,
            academic_year=self.year,
            section=self.section,
            subject=self.subject,
        )
        self.student = Student.objects.create(student_number="TPI-S-1", full_name="طالب المؤشر")
        Enrollment.objects.create(
            student=self.student,
            academic_year=self.year,
            grade=self.grade,
            section=self.section,
            status="active",
        )
        guardian_user = User.objects.create_user("tpi-guardian", password="x")
        family = Family.objects.create(
            school=self.school,
            user=guardian_user,
            guardian_name="ولي المؤشر",
            phone="0790000300",
            family_code="TPI-FAM",
        )
        FamilyStudent.objects.create(family=family, student=self.student)
        TeacherMonthlyEvaluation.objects.create(
            family=family,
            teacher=self.teacher,
            period=self.period,
            teaching_quality_rating=5,
            electronic_services_rating=5,
        )
        TeacherAbsence.objects.create(
            teacher=self.teacher,
            date=date(2026, 7, 5),
            attendance_status="present",
            arrival_time=time(7, 45),
            departure_time=time(14, 0),
            absence_type="excused",
        )
        Homework.objects.create(
            assignment=self.assignment,
            title="واجب TPI",
            description="حل الأسئلة",
            assigned_date=date(2026, 7, 8),
            due_date=date(2026, 7, 10),
            created_by=self.teacher_user,
        )
        semester = self.year.semesters.get(code="second")
        self.exam = Exam.objects.create(
            exam_type="first",
            academic_year=self.year,
            semester=semester,
            grade=self.grade,
            section=self.section,
            subject=self.subject,
            teacher_assignment=self.assignment,
            exam_date=date(2026, 7, 10),
            marks_due_date=date(2026, 7, 15),
            status="open",
        )
        StudentMark.objects.create(exam=self.exam, student=self.student, mark=Decimal("18"), entered_by=self.teacher_user)
        self.exam.status = "closed"
        self.exam.is_locked = True
        self.exam.submitted_by = self.teacher_user
        self.exam.submitted_at = timezone.make_aware(datetime(2026, 7, 14, 10, 0))
        self.exam.published_at = timezone.make_aware(datetime(2026, 7, 16, 10, 0))
        self.exam.save(update_fields=["status", "is_locked", "submitted_by", "submitted_at", "published_at"])
        AttendanceRegister.objects.create(
            academic_year=self.year,
            grade=self.grade,
            section=self.section,
            date=date(2026, 7, 5),
            created_by=self.teacher_user,
            submitted_by=self.teacher_user,
            submitted_at=timezone.make_aware(datetime(2026, 7, 5, 9, 0)),
        )

    def test_tpi_uses_official_work_evidence_and_ranks_teacher(self):
        context = teacher_tpi_context(self.teacher, today=date(2026, 7, 26))
        snapshot = context["snapshot"]
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.rank, 1)
        self.assertGreater(snapshot.score, 0)
        self.assertEqual(snapshot.components["version"], "TPI-131")
        self.assertTrue(snapshot.components["rank_eligible"])
        component_keys = {item["key"] for item in snapshot.components["components"]}
        self.assertEqual(component_keys, {
            "parent_evaluation", "work_attendance", "student_results",
            "success_and_improvement", "homework", "marks_timeliness",
            "student_attendance", "verified_system_activity",
        })

    def test_closed_month_remains_unchanged_after_source_data_changes(self):
        calculation_day = date(2026, 7, 26)
        snapshot = calculate_open_snapshot(self.teacher, self.period, today=calculation_day)
        original_score = snapshot.score
        close_tpi_month(school=self.school, period=self.period, today=calculation_day)
        evaluation = TeacherMonthlyEvaluation.objects.get(teacher=self.teacher, period=self.period)
        evaluation.teaching_quality_rating = 1
        evaluation.save()
        frozen = calculate_open_snapshot(self.teacher, self.period, today=calculation_day)
        self.assertTrue(frozen.is_closed)
        self.assertEqual(frozen.score, original_score)

    def test_attendance_page_view_does_not_create_a_register(self):
        self.client.force_login(self.teacher_user)
        target_date = "2026-07-06"
        response = self.client.get(
            reverse("teachers:portal_attendance_section", args=[self.section.pk]),
            {"date": target_date},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            AttendanceRegister.objects.filter(section=self.section, date=target_date).exists()
        )
    def test_current_month_student_attendance_does_not_expect_future_days(self):
        component, _events, applicable = _student_attendance_component(
            self.teacher, self.period, self.year, date(2026, 7, 5)
        )
        self.assertTrue(applicable)
        # With the configured historical weekend (Thursday/Friday), only
        # July 1, 4 and 5 have elapsed as working days.
        self.assertEqual(component["details"]["expected_registers"], 3)
        self.assertEqual(component["details"]["submitted_registers"], 1)

    def test_missing_exception_rows_mean_present_under_official_policy(self):
        component = _work_attendance_component(
            self.teacher, self.period, self.year, date(2026, 7, 26)
        )
        self.assertTrue(component["available"])
        self.assertEqual(component["score"], 100.0)
        self.assertGreater(component["details"]["implicit_present_days"], 0)
        self.assertEqual(
            component["details"]["evidence_source"],
            "وفق استثناءات الدوام المعتمدة إداريًا",
        )

    def test_complete_elapsed_work_attendance_is_measurable(self):
        for day in (date(2026, 7, 1), date(2026, 7, 4)):
            TeacherAbsence.objects.create(
                teacher=self.teacher,
                date=day,
                attendance_status="present",
                arrival_time=time(7, 45),
                departure_time=time(14, 0),
                absence_type="excused",
            )
        component = _work_attendance_component(
            self.teacher, self.period, self.year, date(2026, 7, 5)
        )
        self.assertTrue(component["available"])
        self.assertEqual(component["score"], 100.0)
        self.assertEqual(component["details"]["implicit_present_days"], 0)
        self.assertEqual(component["details"]["exception_days"], 3)

    def test_academic_improvement_uses_the_previous_official_exam(self):
        previous_exam = Exam.objects.create(
            exam_type="first",
            academic_year=self.year,
            semester=self.year.semesters.get(code="first"),
            grade=self.grade,
            section=self.section,
            subject=self.subject,
            teacher_assignment=self.assignment,
            exam_date=date(2026, 3, 10),
            marks_due_date=date(2026, 3, 15),
            status="closed",
            is_locked=True,
            submitted_by=self.teacher_user,
            submitted_at=timezone.make_aware(datetime(2026, 3, 14, 10, 0)),
            published_at=timezone.make_aware(datetime(2026, 3, 16, 10, 0)),
        )
        StudentMark.objects.create(
            exam=previous_exam,
            student=self.student,
            mark=Decimal("10"),
            entered_by=self.teacher_user,
        )
        metrics = _academic_metrics(self.teacher, self.period)
        self.assertEqual(metrics["compared_students"], 1)
        self.assertGreater(metrics["improvement"], Decimal("50"))

    def test_closed_snapshot_rejects_direct_modification(self):
        close_tpi_month(school=self.school, period=self.period)
        snapshot = self.teacher.tpi_snapshots.get(period=self.period)
        snapshot.score = Decimal("1")
        with self.assertRaises(ValidationError):
            snapshot.save()
