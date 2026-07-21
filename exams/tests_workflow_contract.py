from django.test import SimpleTestCase

from . import workflow


class ExamsWorkflowContractTests(SimpleTestCase):
    def test_complete_exams_workflow_entry_points_exist(self):
        required = {
            "build_gradebook_context",
            "build_exam_definitions_context",
            "build_exam_dashboard_context",
            "build_scope_options_payload",
            "build_mark_list_queryset",
            "build_exam_detail_context",
            "build_student_record_context",
            "build_student_report_card_context",
            "resolve_mark_entry_scope",
            "save_exam_marks",
        }
        self.assertTrue(required.issubset(set(workflow.__all__)))

    def test_official_student_model_is_not_redefined(self):
        self.assertFalse(hasattr(workflow, "StudentRecord"))
