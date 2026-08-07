from __future__ import annotations

from decimal import Decimal

from .models import StudentInvoice, StudentPayment

ZERO = Decimal("0.00")


def build_student_statement_context(student, *, academic_year=None):
    """Build the canonical read-only student statement context.

    The function preserves the current invoice/payment rules while giving the
    accounting workflow one explicit entry point for the statement page.
    """
    invoice_scope = StudentInvoice.objects.filter(student=student)
    payment_scope = StudentPayment.objects.filter(invoice__student=student, status="posted")
    if academic_year is not None:
        invoice_scope = (
            invoice_scope.filter(academic_year=academic_year)
            .exclude(carry_forward_record__source_invoices__isnull=False)
            .distinct()
        )
        payment_scope = (
            payment_scope.filter(invoice__academic_year=academic_year)
            .exclude(invoice__carry_forward_record__source_invoices__isnull=False)
            .distinct()
        )
    invoices = list(
        invoice_scope
        .select_related("fee_category")
        .prefetch_related("payments", "installments")
    )
    payments = list(
        payment_scope
        .select_related("invoice")
    )
    total_invoice = sum(
        (invoice.net_amount for invoice in invoices if invoice.status != "cancelled"),
        ZERO,
    )
    total_payment = sum((payment.amount for payment in payments), ZERO)
    return {
        "student": student,
        "invoices": invoices,
        "payments": payments,
        "total_invoice": total_invoice,
        "total_payment": total_payment,
        "remaining": max(total_invoice - total_payment, ZERO),
        "academic_year": academic_year,
    }
