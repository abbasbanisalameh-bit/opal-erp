from pathlib import Path
from unittest import TestCase


class TimetableWorkflowContractTests(TestCase):
    def test_workflow_entry_points_exist(self):
        source = Path(__file__).with_name("workflow.py").read_text(encoding="utf-8")
        for name in (
            "build_timetable_dashboard_context",
            "build_smart_builder_state",
            "create_absence_coverages",
            "substitute_teacher_is_unavailable",
            "build_print_context",
        ):
            self.assertIn(f"def {name}", source)

    def test_views_use_workflow_layer(self):
        source = Path(__file__).with_name("views.py").read_text(encoding="utf-8")
        self.assertIn("from .workflow import", source)
        self.assertIn("build_timetable_dashboard_context(request)", source)
        self.assertIn("build_smart_builder_state(request)", source)
