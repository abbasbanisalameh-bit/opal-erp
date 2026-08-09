from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class R29GuardianReceiptPolicyContractTests(unittest.TestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_receipts_are_sorted_oldest_to_newest(self):
        source = self.source("parent_portal/receipt_services.py")
        self.assertIn('return sorted(history, key=lambda item: (item["created_at"], item["receipt_number"]))', source)
        self.assertIn('"source_type": source_type', source)
        self.assertIn('"source_id": source_id', source)
        self.assertIn("canonical_accounting_payment_ids", source)
        self.assertIn("exclude(payment_id__in=canonical_accounting_payment_ids)", source)

    def test_parent_history_is_read_only_and_manager_has_print_route(self):
        template = self.source("templates/parent_portal/_guardian_receipt_history.html")
        urls = self.source("parent_portal/urls.py")
        views = self.source("parent_portal/views.py")
        self.assertIn("can_print_receipts", template)
        self.assertIn("family_receipt_print", template)
        self.assertIn("receipt/<str:source_type>/<int:receipt_pk>/print/", urls)
        self.assertIn("def family_receipt_print", views)
        self.assertIn("@management_required", views[views.index("def family_receipt_print") - 100:views.index("def family_receipt_print") + 100])


if __name__ == "__main__":
    unittest.main()
