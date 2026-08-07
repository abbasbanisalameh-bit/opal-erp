from pathlib import Path

from django.test import SimpleTestCase

from core.release_contract_assertions import assert_forward_compatible_release_identity


ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class ReleaseIdentityDeploymentSynchronizationContractTests(SimpleTestCase):
    def test_update_center_explicitly_copies_and_validates_release_identity(self):
        runtime = source("core/update_engine_runtime.py")
        self.assertIn("RELEASE_IDENTITY_FILES", runtime)
        self.assertIn("def _synchronize_release_identity_from_source", runtime)
        self.assertIn("shutil.copy2(source_file, deployed_root / filename)", runtime)
        self.assertIn("manifest.get(\"version_name\") != release_name", runtime)
        self.assertIn("_synchronize_release_identity_from_source(source_root, root)", runtime)

    def test_migration_repairs_all_release_identity_files(self):
        migration = source("core/migrations/0012_r23_release_identity_sync.py")
        self.assertIn("synchronize_release_identity", migration)
        self.assertIn("OPAL_VERSION.txt", migration)
        self.assertIn("OPAL_RELEASE_NAME.txt", migration)
        self.assertIn("OPAL_UPDATE_MANIFEST.json", migration)
        self.assertIn("OPAL Update 131.7 R23 - Release Identity Deployment Synchronization", migration)

    def test_historical_learning_contracts_through_r22_are_forward_compatible(self):
        for revision in range(11, 23):
            matches = sorted((ROOT / "core").glob(f"test_update131_7_r{revision}_*.py"))
            self.assertEqual(len(matches), 1, revision)
            contract = matches[0].read_text(encoding="utf-8")
            self.assertIn("assert_forward_compatible_release_identity", contract, matches[0].name)

    def test_current_release_identity_meets_r23_floor(self):
        assert_forward_compatible_release_identity(self, source, min_revision=26)
