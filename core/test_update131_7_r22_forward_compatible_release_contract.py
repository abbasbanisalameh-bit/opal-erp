from pathlib import Path

from django.test import SimpleTestCase

from core.release_contract_assertions import assert_forward_compatible_release_identity


ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class ForwardCompatibleReleaseContractTests(SimpleTestCase):
    def test_historical_learning_release_contracts_use_shared_forward_compatible_identity(self):
        for revision in range(11, 22):
            matches = sorted((ROOT / "core").glob(f"test_update131_7_r{revision}_*.py"))
            self.assertEqual(len(matches), 1, revision)
            contract = matches[0].read_text(encoding="utf-8")
            self.assertIn(
                "assert_forward_compatible_release_identity",
                contract,
                matches[0].name,
            )
            self.assertNotIn('manifest["baseline"]', contract, matches[0].name)
            self.assertNotIn("self.assertEqual(\n            release_name,", contract, matches[0].name)

    def test_shared_identity_contract_is_forward_compatible(self):
        helper = source("core/release_contract_assertions.py")
        self.assertIn("re.escape(version)", helper)
        self.assertIn('manifest["version_name"]', helper)
        self.assertNotIn('manifest["baseline"]', helper)

    def test_current_release_identity_meets_r22_floor(self):
        assert_forward_compatible_release_identity(
            self,
            source,
            min_revision=25,
        )
