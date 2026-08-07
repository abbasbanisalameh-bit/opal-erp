from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class ProductionReadinessContractTests(SimpleTestCase):
    def test_historical_command_delegates_to_the_canonical_engine(self):
        command = Path(settings.BASE_DIR) / "core/management/commands/audit_production_readiness.py"
        text = command.read_text(encoding="utf-8")

        self.assertIn('call_command(', text)
        self.assertIn('"verify_core_readiness"', text)
        self.assertNotIn(".objects.", text)
        self.assertNotIn("MigrationExecutor", text)
        self.assertNotIn("Student", text)
        self.assertNotIn(".delete()", text)
        self.assertNotIn("flush", text)

    def test_canonical_command_keeps_the_non_destructive_contract(self):
        command = Path(settings.BASE_DIR) / "core/management/commands/verify_core_readiness.py"
        text = command.read_text(encoding="utf-8")

        self.assertIn('"data_deleted": False', text)
        self.assertIn('"database_modified": False', text)
        self.assertIn('"student_model": "students.Student"', text)
        self.assertIn('"version": _opal_release_version(root)', text)
        self.assertIn('OPAL_VERSION.txt', text)
        self.assertNotIn(".delete()", text)
        self.assertNotIn("flush", text)
