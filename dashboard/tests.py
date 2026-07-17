from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from academics.models import Grade, Subject
from accounting.models import FeeCategory, StudentInvoice, StudentPayment
from attendance_v2.models import Attendance
from core.models import AcademicYear, School
from exams.models import Exam, StudentMark
from students.models import Student

from .views import _executive_snapshot


class DashboardPerformanceTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="dashboard-admin",
            password="StrongPass123!",
            is_staff=True,
        )

    def test_snapshot_keeps_the_same_empty_metrics_with_bounded_queries(self):
        with CaptureQueriesContext(connection) as queries:
            snapshot = _executive_snapshot()

        self.assertLessEqual(len(queries), 15)
        self.assertEqual(snapshot["students_count"], 0)
        self.assertEqual(snapshot["total_invoices"], 0)
        self.assertEqual(snapshot["marks_count"], 0)
        self.assertEqual(len(snapshot["attendance_trend"]), 7)

    def test_dashboard_uses_local_chart_library(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vendor/chartjs/chart.umd.min.js")
        self.assertNotContains(response, "https://cdn.jsdelivr.net/npm/chart.js")

    def test_dashboard_response_has_a_bounded_query_count(self):
        self.client.force_login(self.admin)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("dashboard:home"))

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 25)

    def test_optimized_snapshot_preserves_finance_marks_and_attendance_metrics(self):
        school = School.objects.create(name="مدرسة المؤشرات")
        year = AcademicYear.objects.create(
            school=school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        grade = Grade.objects.create(school=school, name="السابع", order=7)
        subject = Subject.objects.create(grade=grade, name="رياضيات", code="M7")
        first_student = Student.objects.create(
            student_number="DASH-1",
            full_name="طالب ناجح",
            grade=grade.name,
        )
        second_student = Student.objects.create(
            student_number="DASH-2",
            full_name="طالب ثانٍ",
            grade=grade.name,
        )

        fee = FeeCategory.objects.create(name="رسوم دراسية", amount=Decimal("100.00"))
        invoice = StudentInvoice.objects.create(
            student=first_student,
            academic_year=year,
            fee_category=fee,
            amount=Decimal("100.00"),
            discount_amount=Decimal("10.00"),
            due_date=timezone.localdate() - timedelta(days=1),
        )
        StudentPayment.objects.create(
            invoice=invoice,
            amount=Decimal("30.00"),
            status="posted",
        )

        exam = Exam.objects.create(
            exam_type="first",
            academic_year=year,
            semester=year.semesters.get(code="first"),
            grade=grade,
            subject=subject,
            status="open",
        )
        StudentMark.objects.create(exam=exam, student=first_student, mark=Decimal("15.00"))
        StudentMark.objects.create(exam=exam, student=second_student, mark=Decimal("10.00"))
        Attendance.objects.create(student=first_student, date=timezone.localdate(), status="present")
        Attendance.objects.create(student=second_student, date=timezone.localdate(), status="absent")

        snapshot = _executive_snapshot()

        self.assertEqual(snapshot["total_invoices"], Decimal("90.00"))
        self.assertEqual(snapshot["paid_amount"], Decimal("30.00"))
        self.assertEqual(snapshot["outstanding"], Decimal("60.00"))
        self.assertEqual(snapshot["overdue_invoices"], 1)
        self.assertEqual(snapshot["marks_count"], 2)
        self.assertEqual(snapshot["pass_rate"], 50.0)
        self.assertEqual(snapshot["present_today"], 1)
        self.assertEqual(snapshot["absent_today"], 1)
        self.assertEqual(snapshot["attendance_percent"], 50)
