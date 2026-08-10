from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]


class R372MobileIndexMigrationConsistencyContractTests(SimpleTestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_model_index_name_matches_migration_0015(self):
        models_source = self.source("core/models.py")
        migration_source = self.source("core/migrations/0015_systemmobileapitoken.py")
        expected = "core_system_user_id_4d66b3_idx"
        self.assertIn(f'name="{expected}"', models_source)
        self.assertIn(f'name="{expected}"', migration_source)

    def test_release_identity_is_r37_2(self):
        self.assertEqual(
            self.source("OPAL_RELEASE_NAME.txt").strip(),
            "OPAL Update 131.7 R37.2 - Mobile Index Migration Consistency Fix",
        )
