from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.dashboard_truth_contracts import run_dashboard_truth_audit


class Update1317R2DashboardTruthContractTests(SimpleTestCase):
    def source(self, relative):
        return (Path(settings.BASE_DIR) / relative).read_text(encoding="utf-8")

    def test_dashboard_queries_are_school_and_year_scoped(self):
        workflow = self.source("dashboard/workflow.py")
        self.assertIn("Teacher.objects.filter(school=school, is_active=True)", workflow)
        self.assertIn("StudentInvoice.objects.filter(academic_year=academic_year)", workflow)
        self.assertIn("exam__academic_year=academic_year", workflow)
        self.assertIn("build_school_attendance_period_snapshot(period_start, today, school=school, academic_year=academic_year)", workflow)
        self.assertNotIn("Student.objects.aggregate(", workflow)
        self.assertNotIn("Section.objects.count()", workflow)

    def test_missing_data_is_not_rendered_as_a_real_zero(self):
        template = self.source("dashboard/templates/dashboard/home.html")
        self.assertIn("لا يوجد سجل حضور معتمد", template)
        self.assertIn("لا توجد رسوم للعام الحالي", template)
        self.assertIn("لا توجد علامات رسمية", template)
        self.assertIn("لم تُعتمد سجلات حضور الشعب اليوم", template)
        self.assertNotIn(':["لا توجد بيانات"]', template)
        self.assertNotIn(":[0]", template)

    def test_satisfaction_participation_and_pair_math_are_exact(self):
        service = self.source("enterprise_ops/services.py")
        self.assertIn("feedback_total = participation_qs.count()", service)
        self.assertIn("both_positive / paired_total", service)
        self.assertIn("feedback_data_available", service)

    def test_production_audit_command_exists(self):
        command = self.source("dashboard/management/commands/audit_dashboard_truth.py")
        self.assertIn("finance_remaining", command)
        self.assertIn("satisfaction_participations_direct", command)
        self.assertIn("latest_students", command)
        self.assertIn("live_grade_event_matrix", command)

    def test_system_contract_passes(self):
        self.assertEqual(run_dashboard_truth_audit()["issues"], [])
