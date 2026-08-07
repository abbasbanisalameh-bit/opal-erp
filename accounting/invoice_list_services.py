from __future__ import annotations

from django.db.models import Q

from .invoice_services import build_invoice_financial_snapshot
from .models import StudentInvoice


def build_invoice_list_context(
    *,
    status="",
    query="",
    overdue=False,
    academic_year=None,
    period=None,
    limit=1000,
):
    """Build the invoice list with an explicit current/previous period filter."""
    invoices = (
        StudentInvoice.objects.select_related("student", "fee_category", "academic_year")
        .prefetch_related("payments")
    )
    status = (status or "").strip()
    query = (query or "").strip()
    normalized_period = (period or "").strip()

    if normalized_period == "current" and academic_year is not None:
        invoices = (
            invoices.filter(academic_year=academic_year)
            .exclude(carry_forward_record__source_invoices__isnull=False)
            .distinct()
        )
    elif normalized_period == "previous" and academic_year is not None:
        invoices = (
            invoices.filter(
                academic_year__school=academic_year.school,
                academic_year__start_date__lt=academic_year.start_date,
            )
            .exclude(carry_forward_record__source_invoices__isnull=False)
            .distinct()
        )
    elif normalized_period == "unassigned":
        invoices = invoices.filter(academic_year__isnull=True)

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

    context = {
        "invoices": items,
        "statuses": StudentInvoice.STATUS_CHOICES,
        "filters": {"status": status, "q": query, "overdue": bool(overdue)},
    }
    if period is not None:
        context["filters"]["period"] = normalized_period
        context["current_year"] = academic_year
    return context
