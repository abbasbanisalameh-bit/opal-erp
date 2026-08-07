from pathlib import Path

from django.test import SimpleTestCase

from core.release_contract_assertions import assert_forward_compatible_release_identity


ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class ProductionLaunchPreparationContractTests(SimpleTestCase):
    def test_service_has_preview_token_transaction_and_preservation_contract(self):
        service = source("core/production_reset.py")
        self.assertIn("PRODUCTION_RESET_CONFIRMATION", service)
        self.assertIn("collect_production_reset_preview", service)
        self.assertIn("execute_production_data_reset", service)
        self.assertIn("transaction.atomic", service)
        self.assertIn("PREVIEW_TOKEN_MAX_AGE_SECONDS", service)
        self.assertIn('"core.School"', service)
        self.assertIn('"core.Branch"', service)
        self.assertIn('"learning_platform.LearningAISettings"', service)
        self.assertIn('"learning_platform.LearningAccount"', service)
        self.assertNotIn('"development_center.Module",', service)

    def test_ui_and_report_are_dedicated_and_exactly_confirmed(self):
        urls = source("core/urls.py")
        views = source("core/production_reset_views.py")
        template = source("templates/core/production_launch_preparation.html")
        settings_template = source("templates/core/system_settings.html")
        self.assertIn("production-launch/", urls)
        self.assertIn("production_reset_report", urls)
        self.assertIn("confirmation != PRODUCTION_RESET_CONFIRMATION", views)
        self.assertIn("preview_token", template)
        self.assertIn("تهيئة التشغيل الفعلي", settings_template)
        self.assertNotIn('name="action" value="reset_all"', settings_template)

    def test_run_model_and_migration_exist(self):
        models = source("core/models.py")
        migration = source("core/migrations/0014_productiondataresetrun.py")
        self.assertIn("class ProductionDataResetRun", models)
        self.assertIn('name="ProductionDataResetRun"', migration)
        self.assertIn("preview_counts", migration)
        self.assertIn("deleted_counts", migration)
        self.assertIn("remaining_counts", migration)

    def test_current_release_identity_meets_r28_floor(self):
        assert_forward_compatible_release_identity(self, source, min_revision=31)
