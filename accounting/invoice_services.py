from decimal import Decimal

ZERO = Decimal("0.00")
HUNDRED = Decimal("100.00")

_STATUS_META = {
    "open": {"label": "غير مدفوعة", "color": "danger"},
    "partial": {"label": "مدفوعة جزئيًا", "color": "warning"},
    "paid": {"label": "مدفوعة بالكامل", "color": "success"},
    "cancelled": {"label": "ملغاة", "color": "secondary"},
}


def build_invoice_financial_snapshot(invoice):
    """Return the canonical read-only financial state for one invoice.

    Only posted payments affect the balance. Cancelled invoices keep their
    cancelled state and expose a zero remaining balance, matching the current
    StudentInvoice rules.
    """
    net_amount = max(getattr(invoice, "net_amount", ZERO) or ZERO, ZERO)
    if getattr(invoice, "status", "open") == "cancelled":
        total_paid = sum(
            (payment.amount for payment in invoice.payments.all() if payment.status == "posted"),
            ZERO,
        )
        status = "cancelled"
        remaining = ZERO
    else:
        total_paid = sum(
            (payment.amount for payment in invoice.payments.all() if payment.status == "posted"),
            ZERO,
        )
        remaining = max(net_amount - total_paid, ZERO)
        if remaining <= ZERO:
            status = "paid"
        elif total_paid > ZERO:
            status = "partial"
        else:
            status = "open"

    if net_amount <= ZERO:
        payment_percentage = HUNDRED if status == "paid" else ZERO
    else:
        payment_percentage = min((total_paid / net_amount) * HUNDRED, HUNDRED)

    meta = _STATUS_META[status]
    return {
        "net_amount": net_amount,
        "total_paid": total_paid,
        "remaining": remaining,
        "payment_percentage": payment_percentage,
        "status": status,
        "status_label": meta["label"],
        "status_color": meta["color"],
    }
