from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]
ATTENDANCE_WORKFLOW = ROOT / "attendance_v2" / "workflow.py"
NOTIFICATION_SERVICES = ROOT / "enterprise_ops" / "services.py"
TIMETABLE_WORKFLOW = ROOT / "timetable" / "workflow.py"
TEACHER_VIEWS = ROOT / "teachers" / "views.py"
PERFORMANCE_HELPERS = ROOT / "core" / "performance_audit.py"


class Update119QueryCollapseContractTests(SimpleTestCase):
    def test_attendance_report_prefetches_section_grade(self):
        source = ATTENDANCE_WORKFLOW.read_text(encoding="utf-8")
        report_block = source[
            source.index("def build_attendance_report_context"):
            source.index("def update_attendance_lock")
        ]
        self.assertIn('"section__grade"', report_block)

    def test_attendance_notifications_are_batched(self):
        workflow = ATTENDANCE_WORKFLOW.read_text(encoding="utf-8")
        services = NOTIFICATION_SERVICES.read_text(encoding="utf-8")
        sync_block = workflow[
            workflow.index("def sync_attendance_registers"):
            workflow.index("def update_register_state")
        ]
        self.assertIn("notify_management_batch", sync_block)
        self.assertNotIn("for register in pending[:100]", sync_block)
        self.assertIn("bulk_create", services)
        self.assertIn("ignore_conflicts=True", services)

    def test_timetable_loads_subject_grade_in_primary_query(self):
        source = TIMETABLE_WORKFLOW.read_text(encoding="utf-8")
        dashboard_block = source[
            source.index("def build_timetable_dashboard_context"):
            source.index("def build_smart_builder_state")
        ]
        self.assertIn('"subject__grade"', dashboard_block)

    def test_teacher_list_loads_linked_user_in_primary_query(self):
        source = TEACHER_VIEWS.read_text(encoding="utf-8")
        teacher_block = source[
            source.index("def teacher_list"):
            source.index("def teacher_create")
        ]
        self.assertIn('select_related("school", "branch", "user")', teacher_block)

    def test_new_runtime_budgets_prevent_n_plus_one_regression(self):
        source = PERFORMANCE_HELPERS.read_text(encoding="utf-8")
        self.assertIn('"key": "attendance_report"', source)
        self.assertIn('"query_budget": 50', source)
        self.assertIn('"key": "teacher_list"', source)
        self.assertIn('"query_budget": 30', source)
        self.assertIn('"key": "timetable_dashboard"', source)
        self.assertIn('"query_budget": 40', source)
