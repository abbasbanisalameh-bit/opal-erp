from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from .invoice_services import build_invoice_financial_snapshot


class _Payments:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class InvoiceFinancialSnapshotContractTests(SimpleTestCase):
    def invoice(self, *, amount="100.00", discount="0.00", status="open", payments=()):
        net = max(Decimal(amount) - Decimal(discount), Decimal("0.00"))
        return SimpleNamespace(
            net_amount=net,
            status=status,
            payments=_Payments(
                [SimpleNamespace(amount=Decimal(value), status=payment_status) for value, payment_status in payments]
            ),
        )

    def test_open_partial_and_paid_states_use_posted_payments_only(self):
        open_snapshot = build_invoice_financial_snapshot(self.invoice())
        partial_snapshot = build_invoice_financial_snapshot(
            self.invoice(payments=(("25.00", "posted"), ("30.00", "deleted")))
        )
        paid_snapshot = build_invoice_financial_snapshot(
            self.invoice(payments=(("120.00", "posted"),))
        )

        self.assertEqual(open_snapshot["status"], "open")
        self.assertEqual(open_snapshot["remaining"], Decimal("100.00"))
        self.assertEqual(partial_snapshot["status"], "partial")
        self.assertEqual(partial_snapshot["total_paid"], Decimal("25.00"))
        self.assertEqual(partial_snapshot["remaining"], Decimal("75.00"))
        self.assertEqual(paid_snapshot["status"], "paid")
        self.assertEqual(paid_snapshot["remaining"], Decimal("0.00"))
        self.assertEqual(paid_snapshot["payment_percentage"], Decimal("100.00"))

    def test_cancelled_invoice_keeps_cancelled_state_and_zero_remaining(self):
        snapshot = build_invoice_financial_snapshot(
            self.invoice(status="cancelled", payments=(("40.00", "posted"),))
        )

        self.assertEqual(snapshot["status"], "cancelled")
        self.assertEqual(snapshot["status_color"], "secondary")
        self.assertEqual(snapshot["remaining"], Decimal("0.00"))

    def test_discounted_invoice_uses_net_amount(self):
        snapshot = build_invoice_financial_snapshot(
            self.invoice(amount="100.00", discount="20.00", payments=(("20.00", "posted"),))
        )

        self.assertEqual(snapshot["net_amount"], Decimal("80.00"))
        self.assertEqual(snapshot["remaining"], Decimal("60.00"))
        self.assertEqual(snapshot["payment_percentage"], Decimal("25.0000"))
