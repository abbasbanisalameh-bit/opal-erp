from pathlib import Path

from django.test import SimpleTestCase

from documents import workflow


class CompleteDocumentWorkflowContractTests(SimpleTestCase):
    def test_complete_document_workflow_exports_stable_entry_points(self):
        for name in (
            "build_document_list_context",
            "build_issue_context",
            "issue_document_from_form",
            "cancel_issued_document",
            "reissue_document",
        ):
            self.assertTrue(callable(getattr(workflow, name)))

    def test_views_delegate_document_lifecycle_to_workflow(self):
        source = Path(__file__).with_name("views.py").read_text()
        self.assertIn("build_document_list_context(", source)
        self.assertIn("build_issue_context(", source)
        self.assertIn("issue_document_from_form(", source)
        self.assertIn("cancel_issued_document(", source)
        self.assertIn("reissue_document(", source)

    def test_workflow_keeps_atomic_mutations(self):
        source = Path(workflow.__file__).read_text()
        self.assertGreaterEqual(source.count("@transaction.atomic"), 3)
