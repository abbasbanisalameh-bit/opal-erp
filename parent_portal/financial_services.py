from decimal import Decimal

from core.models import AcademicYear


ZERO = Decimal("0.00")


def guardian_financial_years(students):
    student_ids = [student.pk for student in students]
    return AcademicYear.objects.filter(student_invoices__student_id__in=student_ids).distinct().order_by("-start_date")


def build_guardian_annual_statement(students, academic_year):
    rows = []
    for student in students:
        invoices = list(student.invoices.filter(academic_year=academic_year).select_related("fee_category").prefetch_related("payments"))
        active = [invoice for invoice in invoices if invoice.status != "cancelled"]
        included = [
            invoice for invoice in invoices
            if invoice.status != "cancelled" or "رُحّل الرصيد" in (invoice.cancellation_reason or "")
        ]
        issued = sum((invoice.net_amount for invoice in included), ZERO)
        paid = sum((invoice.total_paid for invoice in included), ZERO)
        carried_in = sum((invoice.net_amount for invoice in active if hasattr(invoice, "carry_forward_record")), ZERO)
        transactions = []
        for invoice in included:
            transactions.append({
                "date": invoice.issue_date,
                "type": "رسوم" if not hasattr(invoice, "carry_forward_record") else "رصيد مرحل",
                "description": invoice.fee_category.name,
                "debit": invoice.net_amount,
                "credit": ZERO,
                "status": "مغلق ومرحل" if invoice.status == "cancelled" else invoice.get_status_display(),
            })
            for payment in invoice.payments.filter(status="posted"):
                transactions.append({
                    "date": payment.payment_date,
                    "type": "دفعة",
                    "description": payment.get_payment_method_display(),
                    "debit": ZERO,
                    "credit": payment.amount,
                    "status": "معتمدة",
                })
        rows.append({
            "student": student,
            "issued": issued,
            "paid": paid,
            "remaining": sum((invoice.remaining for invoice in active), ZERO),
            "carried_in": carried_in,
            "transactions": sorted(transactions, key=lambda item: (item["date"], item["type"])),
        })
    return {
        "rows": rows,
        "issued": sum((row["issued"] for row in rows), ZERO),
        "paid": sum((row["paid"] for row in rows), ZERO),
        "remaining": sum((row["remaining"] for row in rows), ZERO),
    }
