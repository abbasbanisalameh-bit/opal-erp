from datetime import date

from django.test import RequestFactory, TestCase

from students.models import Student

from .models import Attendance
from .workflow import (
    build_attendance_dashboard_context,
    build_attendance_report_context,
    parse_attendance_date,
)


class AttendanceWorkflowContractTest(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            student_number="ATT-WF-1",
            full_name="طالب اختبار الحضور",
            grade="الأول",
        )
        self.record = Attendance.objects.create(
            student=self.student,
            date=date(2026, 7, 21),
            status="absent",
        )

    def test_dashboard_keeps_unregistered_exception_out_of_authoritative_counts(self):
        context = build_attendance_dashboard_context(target_date=date(2026, 7, 21))
        self.assertEqual(context["total_today"], 0)
        self.assertEqual(context["absent_today"], 0)
        self.assertEqual(context["present_today"], 0)
        self.assertEqual(context["unregistered_exceptions"], 1)

    def test_report_context_preserves_filters_and_results(self):
        params = RequestFactory().get(
            "/attendance/report/",
            {"status": "absent", "q": "اختبار"},
        ).GET
        context = build_attendance_report_context(params=params)
        self.assertEqual(list(context["records"]), [self.record])
        self.assertEqual(context["filters"]["status"], "absent")

    def test_date_parser_keeps_safe_fallback(self):
        fallback = date(2026, 1, 1)
        self.assertEqual(parse_attendance_date("invalid", fallback=fallback), fallback)
