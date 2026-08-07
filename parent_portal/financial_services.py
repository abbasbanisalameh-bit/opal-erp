from decimal import Decimal

from core.models import AcademicYear
from accounting.models import FinancialCarryForward


ZERO = Decimal("0.00")


def guardian_financial_years(students):
    student_ids = [student.pk for student in students]
    invoice_year_ids = AcademicYear.objects.filter(
        student_invoices__student_id__in=student_ids
    ).values_list("pk", flat=True)
    carry_year_ids = FinancialCarryForward.objects.filter(
        student_id__in=student_ids
    ).values_list("closure__target_year_id", flat=True)
    return AcademicYear.objects.filter(pk__in=set(invoice_year_ids) | set(carry_year_ids)).order_by("-start_date")


def build_guardian_annual_statement(students, academic_year):
    """Build one year's statement without merging accumulated prior balances.

    Internal debit/credit compatibility keys are retained for integrations, but
    the official UI uses one amount column and explicit movement types:
    school fee, discount, or payment. Previous-year balances are displayed by
    the dedicated canonical previous-balance service outside this statement.
    """
    rows = []
    for student in students:
        invoices = list(
            student.invoices.filter(academic_year=academic_year)
            .exclude(carry_forward_record__isnull=False)
            .select_related("fee_category")
            .prefetch_related("payments")
        )
        active = [invoice for invoice in invoices if invoice.status != "cancelled"]
        included = [invoice for invoice in invoices if invoice.status != "cancelled"]
        gross_fees = sum((invoice.amount or ZERO for invoice in included), ZERO)
        discounts = sum((invoice.discount_amount or ZERO for invoice in included), ZERO)
        issued = sum((invoice.net_amount for invoice in included), ZERO)
        paid = sum((invoice.total_paid for invoice in included), ZERO)
        transactions = []
        for invoice in included:
            transactions.append({
                "date": invoice.issue_date,
                "type": "رسوم مدرسية",
                "description": invoice.fee_category.name,
                "amount": invoice.amount or ZERO,
                "debit": invoice.net_amount,
                "credit": ZERO,
                "status": invoice.get_status_display(),
            })
            if (invoice.discount_amount or ZERO) > ZERO:
                transactions.append({
                    "date": invoice.issue_date,
                    "type": "خصم",
                    "description": f"خصم على {invoice.fee_category.name}",
                    "amount": invoice.discount_amount,
                    "debit": ZERO,
                    "credit": invoice.discount_amount,
                    "status": "معتمد",
                })
            for payment in invoice.payments.all():
                if payment.status != "posted":
                    continue
                transactions.append({
                    "date": payment.payment_date,
                    "type": "دفعة",
                    "description": payment.get_payment_method_display(),
                    "amount": payment.amount,
                    "debit": ZERO,
                    "credit": payment.amount,
                    "status": "معتمدة",
                })
        remaining = sum((invoice.remaining for invoice in active), ZERO)
        rows.append({
            "student": student,
            "gross_fees": gross_fees,
            "discounts": discounts,
            "issued": issued,
            "paid": paid,
            "remaining": remaining,
            "carried_in": ZERO,
            "total_fees": gross_fees,
            "transactions": sorted(transactions, key=lambda item: (item["date"], item["type"])),
        })
    return {
        "rows": rows,
        "gross_fees": sum((row["gross_fees"] for row in rows), ZERO),
        "discounts": sum((row["discounts"] for row in rows), ZERO),
        "issued": sum((row["issued"] for row in rows), ZERO),
        "paid": sum((row["paid"] for row in rows), ZERO),
        "remaining": sum((row["remaining"] for row in rows), ZERO),
        "carried_in": ZERO,
        "total_fees": sum((row["total_fees"] for row in rows), ZERO),
    }
