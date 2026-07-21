from django.test import SimpleTestCase

from accounting.receipt_services import build_receipt_list_queryset


class ReceiptServicesContractTests(SimpleTestCase):
    def test_receipt_list_builder_is_callable(self):
        self.assertTrue(callable(build_receipt_list_queryset))

    def test_view_uses_canonical_receipt_builder(self):
        from pathlib import Path

        source = Path(__file__).with_name("views.py").read_text(encoding="utf-8")
        self.assertIn("build_receipt_list_queryset()", source)
