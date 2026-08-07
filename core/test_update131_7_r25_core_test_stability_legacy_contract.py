from pathlib import Path

from django.test import SimpleTestCase

from core.release_contract_assertions import assert_forward_compatible_release_identity


ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class CoreTestStabilityLegacyContractTests(SimpleTestCase):
    def test_historical_r14_contract_checks_architecture_not_migration_count(self):
        contract = source("core/test_update131_7_r14_learning_platform_content_management_contract.py")
        self.assertIn('self.assertIn("0001_initial.py", migration_names)', contract)
        self.assertNotIn('self.assertEqual([path.name for path in migrations], ["0001_initial.py"])', contract)
        self.assertIn('for forbidden_model in ("PlatformTeacher", "PlatformStudent")', contract)

    def test_filesystem_heavy_update_tests_ignore_nonfunctional_cleanup_races(self):
        tests = source("core/tests_system_updates.py")
        self.assertGreaterEqual(tests.count("TemporaryDirectory(ignore_cleanup_errors=True)"), 8)
        self.assertIn("test_sqlite_safety_snapshot_restores_the_pre_update_state", tests)
        self.assertIn("test_database_safety_retention_keeps_only_five_latest_snapshots", tests)

    def test_historical_r24_identity_migration_never_downgrades_newer_source(self):
        migration = source("core/migrations/0013_r24_migration_identity_ordering_fix.py")
        self.assertIn('existing_revision > MANIFEST["package_revision"]', migration)
        self.assertIn("current_manifest", migration)
        self.assertIn("return", migration)

    def test_current_release_identity_meets_r25_floor(self):
        assert_forward_compatible_release_identity(self, source, min_revision=28)
