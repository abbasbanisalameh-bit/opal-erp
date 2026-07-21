from django.test import SimpleTestCase

from . import workflow


class ParentPortalWorkflowContractTests(SimpleTestCase):
    def test_public_entry_points_exist(self):
        names = {
            "students_for_user", "family_for_user", "student_for_user_or_403",
            "build_student_card", "build_dashboard_context",
            "build_student_detail_context", "build_fees_context",
            "build_family_finance_context",
        }
        self.assertTrue(all(callable(getattr(workflow, name, None)) for name in names))

    def test_portal_views_delegate_to_workflow(self):
        source = (Path(__file__).with_name("views.py")).read_text(encoding="utf-8")
        self.assertIn("build_dashboard_context(request.user)", source)
        self.assertIn("build_student_detail_context(student)", source)
        self.assertIn("build_fees_context(request.user", source)

from pathlib import Path
