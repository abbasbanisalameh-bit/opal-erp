"""Integrated acceptance tests for the Update 83 lifecycle rules."""

from datetime import date, datetime, time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from academics.models import Enrollment, Grade, Section, StudentLifecycleEvent, Subject
from academics.section_management import merge_sections
from academics.semester_structure import capture_semester_structure
from academics.year_transition import prepare_next_year, execute_annual_transition
from accounting.financial_services import close_financial_year
from accounting.models import (
    FeeCategory,
    FinancialCarryForward,
    StudentInvoice,
    StudentPayment,
)
from admissions.models import GradeFee
from attendance_v2.forms import AttendanceEditForm
from attendance_v2.models import Attendance
from attendance_v2.workflow import save_attendance_edit
from exams.lifecycle import (
    calculate_annual_results,
    close_semester,
    open_exam_cycle,
    reopen_semester,
)
from exams.models import AnnualStudentResult, Exam, ExamCycle, SemesterSubjectResult, StudentMark
from parent_portal.financial_access import guardian_feature_allowed
from parent_portal.models import Family, FamilyStudent
from students.models import Student
from teachers.models import Teacher, TeacherAdvance, TeacherAssignment, TeacherPayroll
from teachers.payroll_services import (
    generate_payroll_period,
    send_payroll,
    terminate_teacher,
)
from timetable.models import TeacherAbsence, TimeSlot, TimetableEntry

from .academic_context import resolve_academic_context
from .models import AcademicYear, Branch, School, SemesterStructureSnapshot


class AcademicContextAcceptanceTests(TestCase):
    def test_date_is_authoritative_and_holidays_have_no_active_semester(self):
        school = School.objects.create(name="مدرسة السياق")
        old_year = AcademicYear.objects.create(
            school=school,
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 6, 30),
            midyear_break_start=date(2026, 1, 16),
            midyear_break_end=date(2026, 1, 31),
            is_current=True,
        )
        new_year = AcademicYear.objects.create(
            school=school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            midyear_break_start=date(2027, 1, 16),
            midyear_break_end=date(2027, 1, 31),
        )

        context = resolve_academic_context(
            school=school,
            reference_date=date(2026, 9, 1),
            persist=True,
        )
        self.assertEqual(context.year, new_year)
        self.assertEqual(context.semester.code, "first")
        old_year.refresh_from_db()
        new_year.refresh_from_db()
        self.assertFalse(old_year.is_current)
        self.assertTrue(new_year.is_current)

        holiday = resolve_academic_context(
            school=school,
            reference_date=date(2027, 1, 20),
            persist=True,
        )
        self.assertEqual(holiday.year, new_year)
        self.assertIsNone(holiday.semester)
        self.assertFalse(new_year.semesters.filter(is_current=True).exists())

        # The second semester is deliberately gated by the formal closure of
        # the first one, even after its calendar start date has arrived.
        first_semester = new_year.semesters.get(code="first")
        first_semester.is_closed = True
        first_semester.save(update_fields=["is_closed"])
        second = resolve_academic_context(
            school=school,
            reference_date=date(2027, 2, 1),
            persist=True,
        )
        self.assertEqual(second.semester.code, "second")


class ExamLifecycleAcceptanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("exam-manager", password="x", is_staff=True)
        self.school = School.objects.create(name="مدرسة الامتحانات")
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            midyear_break_start=date(2027, 1, 16),
            midyear_break_end=date(2027, 1, 31),
        )
        self.grade = Grade.objects.create(school=self.school, name="السابع", order=7)
        self.section = Section.objects.create(
            academic_year=self.year,
            branch=self.branch,
            grade=self.grade,
            name="أ",
        )
        self.subject = Subject.objects.create(academic_year=self.year, grade=self.grade, name="رياضيات")
        self.teacher = Teacher.objects.create(
            employee_number="EX-T-1",
            full_name="معلم الامتحان",
            school=self.school,
        )
        self.assignment = TeacherAssignment.objects.create(
            teacher=self.teacher,
            academic_year=self.year,
            section=self.section,
            subject=self.subject,
        )
        self.student = Student.objects.create(
            student_number="EX-ST-1",
            full_name="طالب الامتحان",
            grade=self.grade.name,
        )
        Enrollment.objects.create(
            student=self.student,
            academic_year=self.year,
            grade=self.grade,
            section=self.section,
            status="active",
        )

    def _complete_term(self, semester, values):
        for exam_type, mark in zip(("first", "second", "third", "final"), values):
            open_exam_cycle(
                academic_year=self.year,
                semester=semester,
                exam_type=exam_type,
                user=self.user,
            )
            exam = Exam.objects.get(
                academic_year=self.year,
                semester=semester,
                section=self.section,
                subject=self.subject,
                exam_type=exam_type,
            )
            StudentMark.objects.create(exam=exam, student=self.student, mark=Decimal(str(mark)))
            Exam.objects.filter(pk=exam.pk).update(status="published", is_locked=True)
        return close_semester(semester=semester, user=self.user)

    def test_cycle_distribution_is_idempotent_and_creates_no_marks(self):
        semester = self.year.semesters.get(code="first")
        first_cycle, first_summary = open_exam_cycle(
            academic_year=self.year,
            semester=semester,
            exam_type="first",
            user=self.user,
        )
        second_cycle, second_summary = open_exam_cycle(
            academic_year=self.year,
            semester=semester,
            exam_type="first",
            user=self.user,
        )

        self.assertEqual(first_cycle, second_cycle)
        self.assertTrue(first_summary["cycle_created"])
        self.assertFalse(second_summary["cycle_created"])
        self.assertEqual(Exam.objects.count(), 1)
        self.assertEqual(StudentMark.objects.count(), 0)

    def test_duplicate_assignment_blocks_cycle_before_any_definition_is_created(self):
        second_teacher = Teacher.objects.create(
            employee_number="EX-T-2",
            full_name="معلم مكرر",
            school=self.school,
        )
        TeacherAssignment.objects.create(
            teacher=second_teacher,
            academic_year=self.year,
            section=self.section,
            subject=self.subject,
        )
        with self.assertRaises(ValidationError):
            open_exam_cycle(
                academic_year=self.year,
                semester=self.year.semesters.get(code="first"),
                exam_type="first",
                user=self.user,
            )
        self.assertFalse(ExamCycle.objects.exists())
        self.assertFalse(Exam.objects.exists())

    def test_closure_blocks_incomplete_term_and_snapshots_annual_average(self):
        first = self.year.semesters.get(code="first")
        open_exam_cycle(
            academic_year=self.year,
            semester=first,
            exam_type="first",
            user=self.user,
        )
        with self.assertRaises(ValidationError):
            close_semester(semester=first, user=self.user)

        self._complete_term(first, (15, 15, 15, 35))
        first_snapshot = SemesterStructureSnapshot.objects.get(semester=first)
        second_seed = SemesterStructureSnapshot.objects.get(
            semester=self.year.semesters.get(code="second")
        )
        self.assertTrue(first_snapshot.is_final)
        self.assertFalse(second_seed.is_final)
        self.assertEqual(second_seed.source_snapshot, first_snapshot)
        self.assertEqual(len(first_snapshot.payload["assignments"]), 1)
        second = self.year.semesters.get(code="second")
        self._complete_term(second, (20, 20, 20, 40))
        second_seed.refresh_from_db()
        self.assertTrue(second_seed.is_final)
        self.assertEqual(
            SemesterSubjectResult.objects.get(semester=first, student=self.student).score,
            Decimal("80.00"),
        )
        self.assertEqual(
            AnnualStudentResult.objects.get(academic_year=self.year, student=self.student).general_average,
            Decimal("90.00"),
        )

        summary = calculate_annual_results(self.year)
        self.assertEqual(summary["student_results"], 1)
        self.assertEqual(
            AnnualStudentResult.objects.get(academic_year=self.year, student=self.student).general_average,
            Decimal("90.00"),
        )

        reopened = reopen_semester(
            semester=second,
            user=self.user,
            reason="تصحيح موثق",
        )
        self.assertFalse(reopened.is_closed)
        self.assertFalse(SemesterSubjectResult.objects.filter(semester=second).exists())
        self.assertFalse(AnnualStudentResult.objects.filter(academic_year=self.year).exists())
        self.assertFalse(
            Exam.objects.filter(semester=second).exclude(status="open", is_locked=False).exists()
        )


class AnnualTransitionAcceptanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("year-manager", password="x", is_staff=True)
        self.school = School.objects.create(name="مدرسة الانتقال")
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.source = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            midyear_break_start=date(2027, 1, 16),
            midyear_break_end=date(2027, 1, 31),
        )
        self.target = AcademicYear.objects.create(
            school=self.school,
            name="2027/2028",
            start_date=date(2027, 9, 1),
            end_date=date(2028, 6, 30),
            midyear_break_start=date(2028, 1, 16),
            midyear_break_end=date(2028, 1, 31),
        )
        self.first_grade = Grade.objects.create(school=self.school, name="الأول", order=1)
        self.final_grade = Grade.objects.create(school=self.school, name="الثاني", order=2)
        self.first_section = Section.objects.create(
            academic_year=self.source,
            branch=self.branch,
            grade=self.first_grade,
            name="أ",
            capacity=30,
        )
        self.final_section = Section.objects.create(
            academic_year=self.source,
            branch=self.branch,
            grade=self.final_grade,
            name="أ",
            capacity=30,
        )
        self.subject = Subject.objects.create(academic_year=self.source, grade=self.first_grade, name="لغة عربية", weekly_periods=5)
        GradeFee.objects.create(
            school=self.school,
            academic_year=self.source,
            grade=self.first_grade,
            tuition_fee=Decimal("500.00"),
        )
        self.teacher = Teacher.objects.create(
            employee_number="YEAR-T-1",
            full_name="معلم التهيئة",
            school=self.school,
        )
        self.assignment = TeacherAssignment.objects.create(
            teacher=self.teacher,
            academic_year=self.source,
            section=self.first_section,
            subject=self.subject,
        )
        self.slot = TimeSlot.objects.create(
            name="حصة التهيئة",
            start_time=time(9, 0),
            end_time=time(9, 45),
            order=2,
        )
        self.timetable_entry = TimetableEntry.objects.create(
            academic_year=self.source,
            section=self.first_section,
            subject=self.subject,
            teacher=self.teacher,
            day="monday",
            time_slot=self.slot,
            room="101",
        )
        self.promoted = Student.objects.create(
            student_number="YEAR-1",
            full_name="طالب مترفع",
            grade=self.first_grade.name,
        )
        self.graduated = Student.objects.create(
            student_number="YEAR-2",
            full_name="طالب متخرج",
            grade=self.final_grade.name,
        )
        Enrollment.objects.create(
            student=self.promoted,
            academic_year=self.source,
            grade=self.first_grade,
            section=self.first_section,
            status="active",
        )
        Enrollment.objects.create(
            student=self.graduated,
            academic_year=self.source,
            grade=self.final_grade,
            section=self.final_section,
            status="active",
        )
        fee = FeeCategory.objects.create(name="رسوم دراسية", amount=Decimal("500.00"))
        self.debt = StudentInvoice.objects.create(
            student=self.promoted,
            academic_year=self.source,
            fee_category=fee,
            amount=Decimal("500.00"),
            due_date=date(2027, 6, 1),
        )

    def test_preparation_copies_structure_only_and_transition_ignores_debt(self):
        invoice_count = StudentInvoice.objects.count()
        capture_semester_structure(
            semester=self.source.semesters.get(code="second"),
            user=self.user,
            final=True,
        )
        AcademicYear.objects.filter(pk=self.source.pk).update(is_closed=True, is_current=False)
        Section.objects.filter(academic_year=self.source).update(is_active=False)
        GradeFee.objects.filter(academic_year=self.source).update(is_active=False)
        Subject.objects.filter(academic_year=self.source).update(is_active=False)
        TeacherAssignment.objects.filter(academic_year=self.source).update(is_active=False)
        TimetableEntry.objects.filter(academic_year=self.source).update(is_active=False)
        self.source.refresh_from_db()
        target, first_summary = prepare_next_year(
            source_year=self.source,
            target_year=self.target,
            user=self.user,
        )
        target, second_summary = prepare_next_year(
            source_year=self.source,
            target_year=self.target,
            user=self.user,
        )

        self.assertIsNotNone(target.prepared_at)
        self.assertEqual(Section.objects.filter(academic_year=self.target).count(), 2)
        self.assertEqual(Enrollment.objects.filter(academic_year=self.target).count(), 0)
        self.assertEqual(StudentInvoice.objects.count(), invoice_count)
        self.assertEqual(GradeFee.objects.filter(academic_year=self.target).count(), 1)
        self.assertEqual(Subject.objects.filter(academic_year=self.target).count(), 1)
        self.assertEqual(TeacherAssignment.objects.filter(academic_year=self.target).count(), 1)
        self.assertEqual(TimetableEntry.objects.filter(academic_year=self.target).count(), 1)
        self.assertFalse(Section.objects.filter(academic_year=self.target, is_active=False).exists())
        self.assertFalse(GradeFee.objects.filter(academic_year=self.target, is_active=False).exists())
        self.assertFalse(Subject.objects.filter(academic_year=self.target, is_active=False).exists())
        self.assertEqual(first_summary["sections_created"], 2)
        self.assertEqual(second_summary["sections_created"], 0)
        self.assertTrue(second_summary["already_prepared"])

        source, result = execute_annual_transition(
            source_year=self.source,
            target_year=self.target,
            user=self.user,
        )
        self.assertEqual(result["promotions"], 1)
        self.assertEqual(result["graduations"], 1)
        promoted_enrollment = Enrollment.objects.get(student=self.promoted, academic_year=self.target)
        self.assertEqual(promoted_enrollment.grade, self.final_grade)
        self.assertEqual(promoted_enrollment.section.name, "شعبة أ")
        self.graduated.refresh_from_db()
        self.assertEqual(self.graduated.status, "graduated")
        self.assertFalse(self.graduated.is_active)
        self.debt.refresh_from_db()
        self.assertEqual(self.debt.status, "open")

        _source, repeated = execute_annual_transition(
            source_year=source,
            target_year=self.target,
            user=self.user,
        )
        self.assertTrue(repeated["already_completed"])
        self.assertEqual(Enrollment.objects.filter(student=self.promoted, academic_year=self.target).count(), 1)


class FinancialClosureAcceptanceTests(TestCase):
    def test_prior_debt_remains_on_original_invoice_without_synthetic_invoice(self):
        user = User.objects.create_user("finance-manager", password="x", is_staff=True)
        school = School.objects.create(name="مدرسة الرسوم")
        source = AcademicYear.objects.create(
            school=school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
        )
        target = AcademicYear.objects.create(
            school=school,
            name="2027/2028",
            start_date=date(2027, 9, 1),
            end_date=date(2028, 6, 30),
        )
        student = Student.objects.create(student_number="FIN-1", full_name="طالب الذمة")
        fee = FeeCategory.objects.create(name="رسوم", amount=Decimal("100.00"))
        invoice = StudentInvoice.objects.create(
            student=student,
            academic_year=source,
            fee_category=fee,
            amount=Decimal("100.00"),
            due_date=date(2027, 6, 1),
        )
        StudentPayment.objects.create(invoice=invoice, amount=Decimal("25.00"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "partial")
        before_count = StudentInvoice.objects.count()
        AcademicYear.objects.filter(pk=source.pk).update(is_closed=True, is_current=False)
        source.refresh_from_db()

        closure = close_financial_year(
            school=school,
            source_year=source,
            target_year=target,
            user=user,
        )
        invoice.refresh_from_db()
        carry = FinancialCarryForward.objects.get(closure=closure, student=student)
        self.assertEqual(StudentInvoice.objects.count(), before_count)
        self.assertEqual(invoice.status, "partial")
        self.assertIsNone(carry.target_invoice)
        self.assertEqual(list(carry.source_invoices.all()), [invoice])
        self.assertEqual(carry.remaining, Decimal("75.00"))

        StudentPayment.objects.create(invoice=invoice, amount=Decimal("75.00"))
        carry = FinancialCarryForward.objects.prefetch_related("source_invoices__payments").get(pk=carry.pk)
        self.assertEqual(carry.remaining, Decimal("0.00"))


class SectionManagementAcceptanceTests(TestCase):
    def test_merge_archives_source_and_preserves_movement_snapshots(self):
        user = User.objects.create_user("section-manager", password="x", is_staff=True)
        school = School.objects.create(name="مدرسة الشعب")
        branch = Branch.objects.create(school=school, name="الرئيسي", is_main=True)
        year = AcademicYear.objects.create(
            school=school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
        )
        grade = Grade.objects.create(school=school, name="الخامس", order=5)
        source = Section.objects.create(
            academic_year=year,
            branch=branch,
            grade=grade,
            name="أ",
        )
        target = Section.objects.create(
            academic_year=year,
            branch=branch,
            grade=grade,
            name="ب",
            capacity=30,
        )
        subject = Subject.objects.create(academic_year=year, grade=grade, name="رياضيات الشعب")
        teacher = Teacher.objects.create(
            employee_number="SEC-T-1",
            full_name="معلم الشعب",
            school=school,
        )
        source_assignment = TeacherAssignment.objects.create(
            teacher=teacher,
            academic_year=year,
            section=source,
            subject=subject,
        )
        slot = TimeSlot.objects.create(
            name="حصة الدمج",
            start_time=time(10, 0),
            end_time=time(10, 45),
            order=3,
        )
        source_entry = TimetableEntry.objects.create(
            academic_year=year,
            section=source,
            subject=subject,
            teacher=teacher,
            day="tuesday",
            time_slot=slot,
        )
        student = Student.objects.create(
            student_number="SEC-ST-1",
            full_name="طالب الدمج",
            grade=grade.name,
            section=source.name,
        )
        enrollment = Enrollment.objects.create(
            student=student,
            academic_year=year,
            grade=grade,
            section=source,
            status="active",
        )

        _source, _target, summary = merge_sections(
            source=source,
            target=target,
            reason="توحيد الشعب لقلة العدد",
            user=user,
            effective_date=date(2026, 10, 1),
        )
        source.refresh_from_db()
        enrollment.refresh_from_db()
        source_assignment.refresh_from_db()
        source_entry.refresh_from_db()
        event = StudentLifecycleEvent.objects.get(student=student, action="section_change")
        self.assertFalse(source.is_active)
        self.assertEqual(enrollment.section, target)
        self.assertEqual(event.from_section_snapshot, "شعبة أ")
        self.assertEqual(event.to_section_snapshot, "شعبة ب")
        self.assertFalse(source_assignment.is_active)
        self.assertTrue(TeacherAssignment.objects.get(section=target, teacher=teacher).is_active)
        self.assertFalse(source_entry.is_active)
        self.assertTrue(TimetableEntry.objects.get(section=target, day="tuesday").is_active)
        self.assertEqual(summary["students_moved"], 1)


class PayrollAndAccessAcceptanceTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("payroll-manager", password="x", is_staff=True)
        self.teacher_user = User.objects.create_user("payroll-teacher", password="x")
        self.school = School.objects.create(name="مدرسة الرواتب")
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_number="PAY-1",
            full_name="معلم الرواتب",
            school=self.school,
            hire_date=date(2025, 9, 1),
            monthly_salary=Decimal("900.00"),
        )

    def test_advance_and_approved_absence_are_deducted_once(self):
        period = date(2026, 7, 1)
        TeacherAbsence.objects.create(
            teacher=self.teacher,
            date=date(2026, 7, 3),
            absence_type="unexcused",
            payroll_approved=True,
            deduction_amount=Decimal("30.00"),
            recorded_by=self.manager,
        )
        advance = TeacherAdvance.objects.create(
            teacher=self.teacher,
            amount=Decimal("100.00"),
            status="acknowledged",
            acknowledged_at=timezone.make_aware(datetime(2026, 7, 5, 10, 0)),
        )

        first = generate_payroll_period(
            school=self.school,
            period=period,
            user=self.manager,
        )
        second = generate_payroll_period(
            school=self.school,
            period=period,
            user=self.manager,
        )
        payroll = TeacherPayroll.objects.get(teacher=self.teacher, period=period)
        self.assertEqual(first["created"], 1)
        self.assertEqual(second["updated"], 1)
        self.assertEqual(payroll.due_date, date(2026, 7, 25))
        self.assertEqual(payroll.advance_deduction, Decimal("100.00"))
        self.assertEqual(payroll.absence_deduction, Decimal("30.00"))
        self.assertEqual(payroll.net_salary, Decimal("770.00"))

        payroll.payment_method = "cash"
        payroll.save(update_fields=["payment_method"])
        with self.captureOnCommitCallbacks(execute=True):
            send_payroll(payroll=payroll, user=self.manager)
        advance.refresh_from_db()
        self.assertEqual(advance.status, "deducted")

        generate_payroll_period(
            school=self.school,
            period=date(2026, 8, 1),
            user=self.manager,
        )
        august = TeacherPayroll.objects.get(teacher=self.teacher, period=date(2026, 8, 1))
        self.assertEqual(august.advance_deduction, Decimal("0.00"))
        self.assertEqual(august.net_salary, Decimal("900.00"))

    def test_termination_is_separate_and_deactivates_operational_links(self):
        branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
        )
        grade = Grade.objects.create(school=self.school, name="الثالث", order=3)
        section = Section.objects.create(
            academic_year=year,
            branch=branch,
            grade=grade,
            name="أ",
        )
        subject = Subject.objects.create(academic_year=year, grade=grade, name="علوم")
        assignment = TeacherAssignment.objects.create(
            teacher=self.teacher,
            academic_year=year,
            section=section,
            subject=subject,
        )
        slot = TimeSlot.objects.create(
            name="الأولى",
            start_time=time(8, 0),
            end_time=time(8, 45),
            order=1,
        )
        entry = TimetableEntry.objects.create(
            academic_year=year,
            section=section,
            subject=subject,
            teacher=self.teacher,
            day="sunday",
            time_slot=slot,
        )

        teacher, termination_document, summary = terminate_teacher(
            teacher=self.teacher,
            end_date=timezone.localdate(),
            reason="انتهاء العقد",
            user=self.manager,
        )
        teacher.refresh_from_db()
        self.teacher_user.refresh_from_db()
        assignment.refresh_from_db()
        entry.refresh_from_db()
        self.assertFalse(teacher.is_active)
        self.assertFalse(self.teacher_user.is_active)
        self.assertFalse(assignment.is_active)
        self.assertFalse(entry.is_active)
        self.assertEqual(termination_document.teacher_id, teacher.pk)
        self.assertEqual(summary["assignments_deactivated"], 1)
        self.assertEqual(summary["timetable_deactivated"], 1)

    def test_guardian_policy_defaults_to_alert_only_and_never_hides_attendance(self):
        student = Student.objects.create(student_number="POLICY-1", full_name="طالب السياسة")
        family = Family.objects.create(school=self.school, guardian_name="ولي الأمر")
        FamilyStudent.objects.create(family=family, student=student)
        fee = FeeCategory.objects.create(name="رسوم السياسة", amount=Decimal("50.00"))
        StudentInvoice.objects.create(
            student=student,
            fee_category=fee,
            amount=Decimal("50.00"),
            due_date=date(2026, 7, 1),
        )

        self.assertEqual(family.financial_policy, "alert_only")
        self.assertTrue(guardian_feature_allowed(family, "marks"))
        family.financial_policy = "hide_results"
        family.save(update_fields=["financial_policy", "updated_at"])
        self.assertFalse(guardian_feature_allowed(family, "marks"))
        self.assertTrue(guardian_feature_allowed(family, "documents"))
        family.financial_policy = "hide_certificates"
        family.save(update_fields=["financial_policy", "updated_at"])
        self.assertFalse(guardian_feature_allowed(family, "documents"))
        self.assertTrue(guardian_feature_allowed(family, "marks"))
        self.assertTrue(guardian_feature_allowed(family, "attendance"))
        self.assertTrue(guardian_feature_allowed(family, "alerts"))

    def test_notification_failure_does_not_rollback_attendance_edit(self):
        student = Student.objects.create(student_number="ATT-SAFE-1", full_name="طالب الحضور")
        record = Attendance.objects.create(
            student=student,
            date=date(2026, 7, 2),
            status="absent",
            recorded_by=self.manager,
        )
        form = AttendanceEditForm({"status": "absent"}, instance=record)
        self.assertTrue(form.is_valid())
        request = RequestFactory().post("/attendance/edit/")
        request.user = self.manager

        with patch(
            "attendance_v2.workflow.notify_parent_for_attendance",
            side_effect=RuntimeError("notification backend unavailable"),
        ), self.captureOnCommitCallbacks(execute=True):
            save_attendance_edit(request=request, form=form)

        record.refresh_from_db()
        self.assertEqual(record.status, "absent")
