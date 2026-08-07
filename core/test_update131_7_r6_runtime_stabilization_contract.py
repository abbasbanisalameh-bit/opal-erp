from datetime import date

from django.test import TestCase

from academics.canonical_services import resolve_section
from academics.models import Grade, Section
from core.models import AcademicYear, Branch, School
from core.operation_audit import build_operation_audit
from dashboard.workflow import build_executive_export_rows


class RuntimeStabilizationContractTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة تثبيت التشغيل", is_active=True)
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        self.grade = Grade.objects.create(school=self.school, name="الصف الأول", order=1)

    def test_operation_audit_builds_without_invalid_subject_outer_reference(self):
        result = build_operation_audit()
        self.assertEqual(result["integration_total_checks"], 19)

    def test_section_resolution_is_idempotent_across_normalized_names(self):
        first, created = resolve_section(
            academic_year=self.year,
            branch=self.branch,
            grade=self.grade,
            name="أ",
        )
        second, created_again = resolve_section(
            academic_year=self.year,
            branch=self.branch,
            grade=self.grade,
            name="  شعبة   أ  ",
        )
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first, second)
        self.assertEqual(Section.objects.count(), 1)

    def test_partial_export_snapshot_reports_unavailable_data_instead_of_crashing(self):
        snapshot = {
            "today": "2026-08-04",
            "students_count": 0,
            "active_students": 0,
            "teachers_count": 0,
            "sections_count": 0,
            "attendance_percent": 0,
            "period_absences": 0,
            "period_departures": 0,
            "total_invoices": 0,
            "paid_amount": 0,
            "outstanding": 0,
            "collection_rate": 0,
            "overdue_invoices": 0,
            "academic_average": 0,
            "pass_rate": 0,
            "issued_documents": 0,
        }
        rows = dict(build_executive_export_rows(snapshot))
        self.assertEqual(rows["نسبة الحضور اليوم"], "لا توجد سجلات معتمدة")
        self.assertEqual(rows["نسبة التحصيل"], "لا توجد رسوم للعام الحالي")
        self.assertEqual(rows["نسبة العلامات المجتازة"], "لا توجد علامات رسمية")
