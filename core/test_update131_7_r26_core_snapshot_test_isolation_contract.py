from pathlib import Path

from django.test import SimpleTestCase

from core.release_contract_assertions import assert_forward_compatible_release_identity


ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class CoreSnapshotTestIsolationContractTests(SimpleTestCase):
    def test_snapshot_tests_do_not_close_the_django_test_connection(self):
        tests = source("core/tests_system_updates.py")
        marker = 'patch(\n                "core.update_engine_runtime.connections.close_all",\n            )'
        self.assertGreaterEqual(tests.count(marker), 3)
        self.assertIn("class DatabaseSafetySnapshotTests(TestCase):", tests)

    def test_low_memory_settings_are_part_of_the_release(self):
        settings_source = source("config/settings_test_low_memory.py")
        self.assertIn("class DisableMigrations(dict):", settings_source)
        self.assertIn('"NAME": "/tmp/opal_r26_low_memory_test.sqlite3"', settings_source)
        self.assertIn("MD5PasswordHasher", settings_source)
        self.assertIn("locmem.EmailBackend", settings_source)

    def test_current_release_identity_meets_r26_floor(self):
        assert_forward_compatible_release_identity(self, source, min_revision=29)
