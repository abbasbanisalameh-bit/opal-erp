"""Canonical entry points for OPAL's school fees and payments workflow.

This module is intentionally a thin orchestration layer. It preserves the
existing models, validation rules, screens, and visual identity while giving
fees, invoices, payments, receipts, and statements one stable internal API.
"""
from __future__ import annotations

from django.db import transaction

from .invoice_list_services import build_invoice_list_context
from .invoice_services import build_invoice_financial_snapshot
from .models import Receipt
from .receipt_services import build_receipt_list_queryset
from .services.receipt import generate_receipt_number
from .statement_services import build_student_statement_context


@transaction.atomic
def create_student_invoice(*, form, user):
    """Create an invoice using the current form/model validation contract."""
    invoice = form.save(commit=False)
    invoice.created_by = user
    invoice.full_clean()
    invoice.save()
    return invoice


@transaction.atomic
def create_student_payment_with_receipt(*, form, user):
    """Create a posted payment and its single canonical receipt atomically."""
    payment = form.save(commit=False)
    payment.created_by = user
    payment.save()
    receipt, _ = Receipt.objects.get_or_create(
        payment=payment,
        defaults={"receipt_number": generate_receipt_number()},
    )
    return payment, receipt


__all__ = [
    "build_invoice_financial_snapshot",
    "build_invoice_list_context",
    "build_receipt_list_queryset",
    "build_student_statement_context",
    "create_student_invoice",
    "create_student_payment_with_receipt",
]
