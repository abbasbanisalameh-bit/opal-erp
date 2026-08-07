from django.test import SimpleTestCase

from accounting.receipt_services import build_receipt_list_queryset


class ReceiptServicesContractTests(SimpleTestCase):
    def test_receipt_list_builder_is_callable(self):
        self.assertTrue(callable(build_receipt_list_queryset))

    def test_receipt_route_redirects_to_the_single_canonical_archive(self):
        from pathlib import Path

        source = Path(__file__).with_name("views.py").read_text(encoding="utf-8")
        self.assertIn('redirect("admissions:fee_payment_archive")', source)
