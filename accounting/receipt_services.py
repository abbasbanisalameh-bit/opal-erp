from __future__ import annotations

from .models import Receipt


def build_receipt_list_queryset():
    """Return the canonical receipt-list queryset.

    Related payment, invoice, and student records are loaded in the same query
    so the receipt screen keeps its current output without per-row lookups.
    """
    return (
        Receipt.objects.select_related(
            "payment",
            "payment__invoice",
            "payment__invoice__student",
        )
        .all()
        .order_by("-created_at")
    )
