import ast
import json
from pathlib import Path

from django.test import SimpleTestCase


from core.release_contract_assertions import assert_forward_compatible_release_identity

ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class LearningPlatformManagerRuntimeFixContractTests(SimpleTestCase):
    def test_manager_view_imports_every_learning_model_it_queries(self):
        views = source("learning_platform/views.py")
        tree = ast.parse(views)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "models" and node.level == 1:
                imported.update(alias.name for alias in node.names)
        self.assertIn("LearningAccount", imported)
        self.assertIn("accounts = LearningAccount.objects.all()", views)

    def test_existing_runtime_test_covers_manager_dashboard_render(self):
        tests = source("learning_platform/tests.py")
        self.assertIn(
            "def test_erp_manager_opens_platform_management_without_learning_account",
            tests,
        )
        self.assertIn("self.assertEqual(response.status_code, 200)", tests)

    def test_r13_release_identity_is_coherent(self):
        assert_forward_compatible_release_identity(
            self,
            source,
            min_revision=16,
        )
