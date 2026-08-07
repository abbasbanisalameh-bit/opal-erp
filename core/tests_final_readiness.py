import io
import json
from datetime import date, time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from academics.lifecycle import perform_lifecycle_action
from academics.models import Enrollment, Grade, Section, Subject
from accounting.models import FeeCategory, StudentInvoice
from admissions.models import GradeFee
from attendance_v2.models import Attendance
from core.academic_years import academic_year_closure_report, activate_academic_year, close_academic_year
from core.models import AcademicYear, Branch, School
from exams.models import Exam, StudentMark
from exams.lifecycle import close_semester
from parent_portal.models import Family, FamilyStudent
from students.models import Student
from teachers.models import Homework, Teacher, TeacherAssignment
from timetable.models import TimeSlot, TimetableEntry


SECURE_TEST_SETTINGS = {
    "DEBUG": False,
    "SECRET_KEY": "opal-tests-production-like-secret-key-with-more-than-fifty-characters-20260717",
}


class AcademicYearClosureTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_superuser("year_manager", "manager@example.test", "pass")
        self.parent_user = User.objects.create_user("year_parent", password="pass")
        self.school = School.objects.create(name="مدرسة دورة العام", is_active=True)
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        self.next_year = AcademicYear.objects.create(
            school=self.school,
            name="2027/2028",
            start_date=date(2027, 9, 1),
            end_date=date(2028, 6, 30),
        )
        self.grade = Grade.objects.create(school=self.school, name="الصف الأول", order=1)
        self.next_grade = Grade.objects.create(school=self.school, name="الصف الثاني", order=2)
        self.section = Section.objects.create(
            academic_year=self.year,
            branch=self.branch,
            grade=self.grade,
            name="أ",
            capacity=30,
        )
        self.next_section = Section.objects.create(
            academic_year=self.next_year,
            branch=self.branch,
            grade=self.next_grade,
            name="أ",
            capacity=30,
        )
        self.student = Student.objects.create(
            student_number="YEAR-001",
            full_name="طالب دورة العام",
            grade=self.grade.name,
            section=self.section.name,
        )
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            academic_year=self.year,
            grade=self.grade,
            section=self.section,
            status="active",
        )
        self.subject = Subject.objects.create(academic_year=self.year, name="الرياضيات", code="YR-MATH", grade=self.grade, weekly_periods=5)
        self.exam = Exam.objects.create(
            exam_type="first",
            academic_year=self.year,
            semester=self.year.semesters.get(code="first"),
            grade=self.grade,
            subject=self.subject,
            status="open",
        )
        StudentMark.objects.create(exam=self.exam, student=self.student, mark=Decimal("18.00"))
        self.exam.status = "closed"
        self.exam.is_locked = True
        self.exam.save()

    def test_active_enrollment_blocks_year_closure(self):
        report = academic_year_closure_report(self.year)
        self.assertTrue(report["blockers"])
        with self.assertRaises(ValidationError):
            close_academic_year(year=self.year, user=self.manager)
        self.year.refresh_from_db()
        self.assertFalse(self.year.is_closed)

    def test_closure_locks_operations_preserves_finance_and_parent_results(self):
        teacher = Teacher.objects.create(
            employee_number="YEAR-T-1",
            full_name="معلم دورة العام",
            school=self.school,
            branch=self.branch,
        )
        assignment = TeacherAssignment.objects.create(
            teacher=teacher,
            academic_year=self.year,
            section=self.section,
            subject=self.subject,
        )
        homework = Homework.objects.create(
            assignment=assignment,
            title="واجب ختامي",
            description="مراجعة",
            assigned_date=date(2027, 6, 1),
            due_date=date(2027, 6, 5),
            created_by=self.manager,
        )
        slot = TimeSlot.objects.create(
            name="الحصة الأولى",
            start_time=time(8, 0),
            end_time=time(8, 45),
            order=1,
        )
        timetable = TimetableEntry.objects.create(
            academic_year=self.year,
            section=self.section,
            subject=self.subject,
            teacher=teacher,
            day="sunday",
            time_slot=slot,
        )
        attendance = Attendance.objects.create(
            student=self.student,
            academic_year=self.year,
            grade=self.grade,
            section=self.section,
            date=date(2027, 6, 1),
            status="absent",
        )
        grade_fee = GradeFee.objects.create(
            school=self.school,
            academic_year=self.year,
            grade=self.grade,
            tuition_fee=Decimal("1000.00"),
        )
        category = FeeCategory.objects.create(name="رسوم العام", amount=Decimal("1000.00"))
        invoice = StudentInvoice.objects.create(
            student=self.student,
            academic_year=self.year,
            fee_category=category,
            amount=Decimal("1000.00"),
            due_date=date(2027, 6, 30),
        )
        family = Family.objects.create(
            user=self.parent_user,
            school=self.school,
            guardian_name="ولي طالب دورة العام",
        )
        FamilyStudent.objects.create(family=family, student=self.student)

        for semester in self.year.semesters.all():
            for exam_type in dict(Exam.EXAM_TYPES):
                exam = Exam.objects.create(
                    exam_type=exam_type,
                    academic_year=self.year,
                    semester=semester,
                    grade=self.grade,
                    section=self.section,
                    subject=self.subject,
                    teacher_assignment=assignment,
                    status="published",
                    is_locked=True,
                )
                StudentMark.objects.create(exam=exam, student=self.student, mark=exam.max_mark)
            close_semester(semester=semester, user=self.manager)

        with patch("core.academic_years.timezone.localdate", return_value=date(2027, 7, 1)):
            closed_year, summary = close_academic_year(
                year=self.year,
                user=self.manager,
                notes="اعتماد نهاية العام",
            )
        perform_lifecycle_action(
            student=self.student,
            action="promote",
            effective_date=date(2027, 7, 1),
            target_year=self.next_year,
            target_grade=self.next_grade,
            target_section=self.next_section,
            user=self.manager,
        )

        closed_year.refresh_from_db()
        attendance.refresh_from_db()
        assignment.refresh_from_db()
        homework.refresh_from_db()
        timetable.refresh_from_db()
        self.section.refresh_from_db()
        self.subject.refresh_from_db()
        grade_fee.refresh_from_db()
        invoice.refresh_from_db()
        self.assertTrue(closed_year.is_closed)
        self.assertFalse(closed_year.is_current)
        self.assertEqual(closed_year.closed_by, self.manager)
        self.assertTrue(attendance.is_locked)
        self.assertFalse(assignment.is_active)
        self.assertFalse(homework.is_active)
        self.assertFalse(timetable.is_active)
        self.assertFalse(self.section.is_active)
        self.assertFalse(self.subject.is_active)
        self.assertFalse(grade_fee.is_active)
        self.assertEqual(invoice.status, "open")
        self.assertEqual(summary["attendance_locked"], 1)

        # After promotion, the parent portal correctly defaults to the new
        # academic year; verify the previous year's published result remains
        # stored rather than assuming it appears in the new-year matrix.
        self.assertTrue(StudentMark.objects.filter(exam=self.exam, student=self.student).exists())

        self.section.is_active = True
        with self.assertRaises(ValidationError):
            self.section.save()

    def test_activate_open_year_and_reject_closed_year(self):
        activated = activate_academic_year(year=self.next_year)
        self.year.refresh_from_db()
        self.assertTrue(activated.is_current)
        self.assertFalse(self.year.is_current)
        # No semester is made active outside its official date boundaries.
        self.assertEqual(activated.semesters.filter(is_current=True).count(), 0)

        AcademicYear.objects.filter(pk=self.year.pk).update(is_closed=True, is_current=False)
        self.year.refresh_from_db()
        with self.assertRaises(ValidationError):
            activate_academic_year(year=self.year)


class FinalPermissionAndErrorPageTests(TestCase):
    def setUp(self):
        self.plain_user = User.objects.create_user("plain_academic_user", password="pass")
        self.superuser = User.objects.create_superuser("final_owner", "owner@example.test", "pass")

    def test_plain_authenticated_user_cannot_manage_academic_years(self):
        self.client.force_login(self.plain_user)
        response = self.client.get(reverse("academics:academic_year_list"))
        self.assertRedirects(response, reverse("dashboard:home"), fetch_redirect_response=False)

    @override_settings(DEBUG=False)
    def test_production_404_is_friendly_and_hides_django_diagnostics(self):
        response = self.client.get("/route-that-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "الصفحة غير موجودة", status_code=404)
        self.assertNotContains(response, "Using the URLconf", status_code=404)


class AcademicYearViewFlowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser("year_view_owner", "year-view@example.test", "pass")
        self.school = School.objects.create(name="مدرسة شاشة الأعوام", is_active=True)
        Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.client.force_login(self.owner)

    def test_create_year_from_year_list_builds_exactly_two_semesters(self):
        response = self.client.post(
            reverse("academics:academic_year_create"),
            {
                "name": "2028/2029",
                "start_date": "2028-09-01",
                "first_semester_end": "2029-01-15",
                "second_semester_start": "2029-02-01",
                "end_date": "2029-06-30",
                "is_current": "on",
            },
        )
        year = AcademicYear.objects.get(school=self.school, name="2028/2029")
        self.assertRedirects(
            response,
            f"{reverse('academics:academic_structure')}?year={year.pk}",
        )
        self.assertEqual(set(year.semesters.values_list("code", flat=True)), {"first", "second"})

    def test_close_page_renders_blockers_and_closed_structure_is_read_only(self):
        year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        grade = Grade.objects.create(school=self.school, name="الصف الأول")
        section = Section.objects.create(
            academic_year=year,
            branch=self.school.branches.first(),
            grade=grade,
            name="أ",
        )
        student = Student.objects.create(student_number="VIEW-1", full_name="طالب الشاشة", grade=grade.name)
        Enrollment.objects.create(
            student=student,
            academic_year=year,
            grade=grade,
            section=section,
            status="active",
        )
        response = self.client.get(reverse("academics:academic_year_close", args=[year.pk]))
        self.assertContains(response, "لا يمكن إغلاق العام حاليًا")

        AcademicYear.objects.filter(pk=year.pk).update(is_closed=True, is_current=False)
        response = self.client.get(f"{reverse('academics:academic_structure')}?year={year.pk}")
        self.assertContains(response, "الهيكل معروض كسجل تاريخي")
        self.assertNotContains(response, "حفظ الصف والرسوم والشعب")


class ReadinessCommandTests(TestCase):
    @override_settings(**SECURE_TEST_SETTINGS)
    def test_allow_empty_returns_machine_readable_report_without_failure(self):
        output = io.StringIO()
        call_command("verify_core_readiness", allow_empty=True, format="json", stdout=output)
        report = json.loads(output.getvalue())
        self.assertTrue(report["ready"])
        self.assertEqual(report["summary"]["errors"], 0)
        self.assertGreater(report["summary"]["warnings"], 0)

    @override_settings(**SECURE_TEST_SETTINGS)
    def test_closed_current_year_is_a_critical_readiness_error(self):
        User.objects.create_superuser("readiness_owner", "ready@example.test", "pass")
        school = School.objects.create(name="مدرسة الفحص", is_active=True)
        Branch.objects.create(school=school, name="الرئيسي", is_main=True)
        year = AcademicYear.objects.create(
            school=school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        AcademicYear.objects.filter(pk=year.pk).update(is_closed=True, is_current=True)
        output = io.StringIO()
        with self.assertRaises(CommandError):
            call_command("verify_core_readiness", format="text", stdout=output)
        self.assertIn("CORE_CLOSED_CURRENT_YEAR", output.getvalue())
