from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from .live_operations_contracts import run_live_operations_repair_audit


class Update1312LiveOperationsContractTests(SimpleTestCase):
    def source(self, relative):
        return (Path(settings.BASE_DIR) / relative).read_text(encoding="utf-8")

    def test_live_operations_audit_passes(self):
        report = run_live_operations_repair_audit(Path(settings.BASE_DIR))
        self.assertTrue(report["ok"], report["issues"])

    def test_weekly_matrix_scopes_exception_to_today(self):
        attendance = self.source("timetable/attendance_services.py")
        workflow = self.source("timetable/workflow.py")
        self.assertIn("decorate_weekly_entries_with_current_status", attendance)
        self.assertIn("item.day == current_day_code", attendance)
        self.assertIn("decorate_weekly_entries_with_current_status(", workflow)

    def test_director_dashboard_has_grade_and_teacher_live_blocks(self):
        dashboard = self.source("dashboard/workflow.py")
        template = self.source("dashboard/templates/dashboard/home.html")
        self.assertIn('"opal_live_schedule": management_live_status(school)', dashboard)
        self.assertIn("opal_live_schedule.grade_columns", template)
        self.assertIn("opal_live_schedule.busy_rows", template)
        self.assertIn("opal_live_schedule.free_teachers", template)
