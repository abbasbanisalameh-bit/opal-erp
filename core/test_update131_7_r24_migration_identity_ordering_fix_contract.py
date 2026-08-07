from pathlib import Path

from django.test import SimpleTestCase

from core.release_contract_assertions import assert_forward_compatible_release_identity


ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class MigrationIdentityOrderingFixContractTests(SimpleTestCase):
    def test_r21_manifest_migration_never_downgrades_a_newer_release(self):
        migration = source("learning_platform/migrations/0007_r21_runtime_validation_fixes.py")
        self.assertIn('existing_revision > MANIFEST["package_revision"]', migration)
        self.assertIn("current_manifest", migration)
        self.assertIn("return", migration)

    def test_r24_finalizer_runs_after_the_historical_r21_manifest_migration(self):
        migration = source("core/migrations/0013_r24_migration_identity_ordering_fix.py")
        self.assertIn('("core", "0012_r23_release_identity_sync")', migration)
        self.assertIn('("learning_platform", "0007_r21_runtime_validation_fixes")', migration)
        self.assertIn("finalize_release_identity", migration)
        self.assertIn("OPAL Update 131.7 R24 - Migration Identity Ordering Fix", migration)

    def test_historical_learning_contracts_through_r23_are_forward_compatible(self):
        for revision in range(11, 24):
            matches = sorted((ROOT / "core").glob(f"test_update131_7_r{revision}_*.py"))
            self.assertEqual(len(matches), 1, revision)
            contract = matches[0].read_text(encoding="utf-8")
            self.assertIn("assert_forward_compatible_release_identity", contract, matches[0].name)

    def test_current_release_identity_meets_r24_floor(self):
        assert_forward_compatible_release_identity(self, source, min_revision=27)
