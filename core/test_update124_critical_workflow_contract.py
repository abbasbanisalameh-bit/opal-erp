from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.critical_workflow_contracts import (
    audit_parent_communication_contract,
    audit_receipt_print_contract,
    audit_teacher_lifecycle_contract,
    run_critical_workflow_contract_audit,
)


class Update124CriticalWorkflowContractTests(SimpleTestCase):
    def test_parent_communication_contract_is_complete(self):
        self.assertEqual(audit_parent_communication_contract(), [])

    def test_teacher_lifecycle_contract_is_complete(self):
        self.assertEqual(audit_teacher_lifecycle_contract(), [])

    def test_receipts_are_standalone_two_copy_landscape_documents(self):
        self.assertEqual(audit_receipt_print_contract(), [])

    def test_combined_critical_workflow_gate_is_read_only_and_ok(self):
        report = run_critical_workflow_contract_audit()
        self.assertEqual(set(report), {"ok", "checks", "issue_count", "issues"})
        self.assertTrue(report["ok"])
        self.assertEqual(report["issue_count"], 0)

    def test_teacher_detail_exposes_latest_termination_letter_without_new_page(self):
        source = (Path(settings.BASE_DIR) / "templates/teachers/teacher_detail.html").read_text(encoding="utf-8")
        self.assertIn("latest_termination_document", source)
        self.assertIn("documents:document_detail", source)
