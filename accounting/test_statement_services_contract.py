from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from .statement_services import build_student_statement_context


class StudentStatementServiceContractTests(SimpleTestCase):
    def _chain(self, values):
        queryset = MagicMock()
        queryset.select_related.return_value = queryset
        queryset.prefetch_related.return_value = values
        return queryset

    @patch("accounting.statement_services.StudentPayment.objects.filter")
    @patch("accounting.statement_services.StudentInvoice.objects.filter")
    def test_statement_context_preserves_totals_and_excludes_cancelled_invoices(
        self, invoice_filter, payment_filter
    ):
        student = object()
        invoices = [
            SimpleNamespace(net_amount=Decimal("1000.00"), status="issued"),
            SimpleNamespace(net_amount=Decimal("250.00"), status="cancelled"),
        ]
        payments = [SimpleNamespace(amount=Decimal("400.00"))]
        invoice_filter.return_value = self._chain(invoices)
        payment_queryset = MagicMock()
        payment_queryset.select_related.return_value = payments
        payment_filter.return_value = payment_queryset

        context = build_student_statement_context(student)

        self.assertIs(context["student"], student)
        self.assertEqual(context["invoices"], invoices)
        self.assertEqual(context["payments"], payments)
        self.assertEqual(context["total_invoice"], Decimal("1000.00"))
        self.assertEqual(context["total_payment"], Decimal("400.00"))
        self.assertEqual(context["remaining"], Decimal("600.00"))

    @patch("accounting.statement_services.StudentPayment.objects.filter")
    @patch("accounting.statement_services.StudentInvoice.objects.filter")
    def test_remaining_never_becomes_negative(self, invoice_filter, payment_filter):
        student = object()
        invoices = [SimpleNamespace(net_amount=Decimal("100.00"), status="issued")]
        payments = [SimpleNamespace(amount=Decimal("150.00"))]
        invoice_filter.return_value = self._chain(invoices)
        payment_queryset = MagicMock()
        payment_queryset.select_related.return_value = payments
        payment_filter.return_value = payment_queryset

        context = build_student_statement_context(student)

        self.assertEqual(context["remaining"], Decimal("0.00"))
