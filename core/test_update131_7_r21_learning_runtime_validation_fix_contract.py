import json
from pathlib import Path

from django.test import SimpleTestCase


from core.release_contract_assertions import assert_forward_compatible_release_identity

ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class LearningRuntimeValidationFixContractTests(SimpleTestCase):
    def test_brittle_translation_assertion_is_removed(self):
        tests = source("learning_platform/tests.py")
        self.assertIn('form = response.context["form"]', tests)
        self.assertIn('self.assertIn("course", form.errors)', tests)
        self.assertNotIn('self.assertContains(response, "اختر اختيارًا صحيحًا")', tests)

    def test_mobile_api_contract_uses_django_meta_header(self):
        contract = source("core/test_update131_7_r20_learning_production_release_contract.py")
        self.assertIn('request.META.get("HTTP_AUTHORIZATION")', contract)
        self.assertIn('startswith("bearer ")', contract)

    def test_update_center_copies_manifest_and_migration_repairs_current_deployment(self):
        runtime = source("core/update_engine_runtime.py")
        migration = source("learning_platform/migrations/0007_r21_runtime_validation_fixes.py")
        self.assertNotIn("child.name == MANIFEST_NAME", runtime)
        self.assertIn("restore_release_manifest", migration)
        self.assertIn("OPAL_UPDATE_MANIFEST.json", migration)

    def test_r21_release_identity_is_coherent(self):
        assert_forward_compatible_release_identity(
            self,
            source,
            min_revision=24,
        )
