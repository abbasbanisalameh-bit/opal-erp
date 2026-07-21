from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from . import workflow


class FinanceWorkflowContractTests(SimpleTestCase):
    def test_workflow_exports_complete_school_fee_read_api(self):
        self.assertTrue(callable(workflow.build_invoice_financial_snapshot))
        self.assertTrue(callable(workflow.build_invoice_list_context))
        self.assertTrue(callable(workflow.build_receipt_list_queryset))
        self.assertTrue(callable(workflow.build_student_statement_context))

    @patch("accounting.workflow.Receipt.objects.get_or_create")
    @patch("accounting.workflow.generate_receipt_number", return_value="REC-TEST")
    def test_payment_and_receipt_are_created_through_one_entry_point(self, number, get_or_create):
        payment = Mock(pk=10)
        form = Mock()
        form.save.return_value = payment
        receipt = Mock(receipt_number="REC-TEST")
        get_or_create.return_value = (receipt, True)

        created_payment, created_receipt = workflow.create_student_payment_with_receipt(
            form=form,
            user=Mock(),
        )

        payment.save.assert_called_once_with()
        get_or_create.assert_called_once_with(
            payment=payment,
            defaults={"receipt_number": "REC-TEST"},
        )
        self.assertIs(created_payment, payment)
        self.assertIs(created_receipt, receipt)

    def test_invoice_creation_preserves_model_validation(self):
        invoice = Mock(pk=11)
        form = Mock()
        form.save.return_value = invoice
        user = Mock()

        result = workflow.create_student_invoice(form=form, user=user)

        self.assertIs(invoice.created_by, user)
        invoice.full_clean.assert_called_once_with()
        invoice.save.assert_called_once_with()
        self.assertIs(result, invoice)
