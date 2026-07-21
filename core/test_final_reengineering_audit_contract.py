from pathlib import Path

from django.test import SimpleTestCase, override_settings

from core.final_reengineering_audit import (
    audit_official_student_model,
    audit_required_identity_files,
    run_final_reengineering_audit,
)


class FinalReengineeringAuditContractTests(SimpleTestCase):
    def test_official_student_model_remains_unique(self):
        self.assertEqual(audit_official_student_model(), [])

    def test_identity_audit_reports_missing_files_without_mutation(self):
        with self.settings(BASE_DIR=Path("/tmp/opal-nonexistent-audit-root")):
            issues = audit_required_identity_files()
        self.assertEqual(len(issues), 3)
        self.assertTrue(all(issue.code == "opal_identity_file_missing" for issue in issues))

    def test_audit_contract_has_stable_keys(self):
        report = run_final_reengineering_audit(include_templates=False)
        self.assertEqual(set(report), {"ok", "checks", "issue_count", "issues"})
        self.assertIn("official_student_model", report["checks"])
        self.assertIn("named_urls", report["checks"])
