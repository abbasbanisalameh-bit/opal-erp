import json
import re
from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class ProductionCloseoutContractTests(SimpleTestCase):
    def test_release_identity_is_coherent_and_final_revision_is_monotonic(self):
        release_name = source("OPAL_RELEASE_NAME.txt").strip()
        manifest = json.loads(source("OPAL_UPDATE_MANIFEST.json"))
        self.assertEqual(source("OPAL_VERSION.txt").strip(), "131.7")
        self.assertEqual(manifest["version"], "131.7")
        self.assertEqual(manifest["version_name"], release_name)
        self.assertGreaterEqual(manifest["package_revision"], 13)
        self.assertTrue(manifest["code_only"])

    def test_primary_assets_share_the_final_nonempty_cache_token(self):
        tokens = re.findall(
            r"(?:opal_erp\.css|opal_dashboard_executive\.css|opal_entity_360_consolidation\.css|opal_erp\.js)' %\}\?v=([^\"\s]+)",
            source("templates/base/base.html"),
        )
        self.assertEqual(len(tokens), 4)
        self.assertEqual(len(set(tokens)), 1)
        self.assertIn("update1317-r10-aesthetic-finishing", tokens[0])

    def test_backup_recovery_report_reads_the_canonical_release_version(self):
        command = source("core/management/commands/audit_backup_recovery.py")
        self.assertIn('(root / "OPAL_VERSION.txt").read_text', command)
        self.assertNotIn('"version": "77"', command)

    def test_closeout_documents_are_present(self):
        for relative in (
            "INSTALL_OPAL_UPDATE_131_7_R9_PRODUCTION_CLOSEOUT_AR.md",
            "OPAL_UPDATE_131_7_R9_PRODUCTION_CLOSEOUT_RELEASE_NOTES_AR.md",
            "OPAL_UPDATE_131_7_R9_VALIDATION_REPORT_AR.md",
            "OPAL_PRODUCTION_ENVIRONMENT_CHECKLIST_R9_AR.md",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)
