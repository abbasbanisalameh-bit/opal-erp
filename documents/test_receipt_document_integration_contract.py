from django.test import SimpleTestCase

from accounting import workflow as finance_workflow


class ReceiptDocumentIntegrationContractTests(SimpleTestCase):
    def test_receipt_flow_remains_canonical_and_available(self):
        self.assertTrue(callable(finance_workflow.create_student_payment_with_receipt))
        self.assertTrue(callable(finance_workflow.build_receipt_list_queryset))
