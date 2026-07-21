from __future__ import annotations

from django.db.models import Q

from .invoice_services import build_invoice_financial_snapshot
from .models import StudentInvoice


def build_invoice_list_context(*, status="", query="", overdue=False, limit=1000):
    """Build the canonical invoice-list context without changing list behavior."""
    invoices = (
        StudentInvoice.objects.select_related("student", "fee_category", "academic_year")
        .prefetch_related("payments")
    )
    status = (status or "").strip()
    query = (query or "").strip()

    if status:
        invoices = invoices.filter(status=status)
    if query:
        invoices = invoices.filter(
            Q(student__full_name__icontains=query)
            | Q(student__student_number__icontains=query)
            | Q(invoice_number__icontains=query)
        )

    items = list(invoices[:limit])
    for invoice in items:
        invoice.financial_snapshot = build_invoice_financial_snapshot(invoice)

    if overdue:
        items = [invoice for invoice in items if invoice.is_overdue]

    return {
        "invoices": items,
        "statuses": StudentInvoice.STATUS_CHOICES,
        "filters": {"status": status, "q": query, "overdue": bool(overdue)},
    }
