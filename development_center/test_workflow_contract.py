from django.test import SimpleTestCase

from development_center import workflow


class DevelopmentCenterWorkflowContractTests(SimpleTestCase):
    def test_unified_entry_points_exist(self):
        expected = [
            "build_development_dashboard_context",
            "build_tasks_board_context",
            "build_roadmap_context",
            "build_sprint_detail_context",
            "build_notifications_context",
        ]
        for name in expected:
            self.assertTrue(callable(getattr(workflow, name, None)), name)

    def test_workflow_has_no_new_models(self):
        self.assertFalse(hasattr(workflow, "models"))
