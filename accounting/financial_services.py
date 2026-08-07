from __future__ import annotations

import calendar
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from admissions.models import FeePayment, StudentRegistration
from core.academic_context import current_academic_year
from core.models import AcademicYear

from .models import (
    ExpenseEntry,
    CanteenTransaction,
    FeeCategory,
    FinancialCarryForward,
    FinancialYearClosure,
    MonthlyFinancialTarget,
    MonthlyFinancialStatement,
    Receipt,
    StudentInvoice,
    StudentPayment,
)


ZERO = Decimal("0.00")


def financial_period(reference=None):
    """Return the inclusive calendar month: first day through the actual last day."""
    reference = reference or timezone.localdate()
    last_day = calendar.monthrange(reference.year, reference.month)[1]
    period_start = reference.replace(day=1)
    period_end = reference.replace(day=last_day)
    return period_start, period_end


def normalize_period_end(value=None):
    if not value:
        return financial_period()[1]
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError as exc:
            raise ValidationError("تاريخ الشهر المالي غير صحيح.") from exc
    last_day = calendar.monthrange(value.year, value.month)[1]
    return value.replace(day=last_day)


def _income_rows(school, period_start, period_end):
    rows = []
    canonical = FeePayment.objects.filter(
        school=school,
        is_deleted=False,
        created_at__date__range=(period_start, period_end),
    ).select_related("main_student", "created_by")
    for item in canonical:
        rows.append({
            "date": timezone.localtime(item.created_at),
            "number": item.receipt_number,
            "description": f"{item.payment_period_label} — {item.get_scope_display()}",
            "party": item.guardian_name or getattr(item.main_student, "full_name", ""),
            "method": item.get_payment_method_display(),
            "receiver": item.created_by.get_full_name() or item.created_by.username if item.created_by else "النظام",
            "amount": item.total_amount,
        })

    registrations = list(StudentRegistration.objects.filter(
        school=school,
        receipt__isnull=False,
        payment__status="posted",
        receipt__created_at__date__range=(period_start, period_end),
    ).select_related("student", "receipt", "payment", "created_by"))
    registration_receipt_ids = [item.receipt_id for item in registrations]
    for item in registrations:
        rows.append({
            "date": timezone.localtime(item.receipt.created_at),
            "number": item.receipt.receipt_number,
            "description": "دفعة التسجيل الأولى",
            "party": item.full_name,
            "method": item.get_payment_method_display(),
            "receiver": item.created_by.get_full_name() or item.created_by.username if item.created_by else "النظام",
            "amount": item.first_payment,
        })

    legacy = Receipt.objects.filter(
        payment__status="posted",
        created_at__date__range=(period_start, period_end),
    ).exclude(pk__in=registration_receipt_ids).select_related(
        "payment", "payment__invoice__student", "payment__created_by"
    )
    for item in legacy:
        payment = item.payment
        rows.append({
            "date": timezone.localtime(item.created_at),
            "number": item.receipt_number,
            "description": "دفعة رسوم سابقة",
            "party": payment.invoice.student.full_name,
            "method": payment.get_payment_method_display(),
            "receiver": payment.created_by.get_full_name() or payment.created_by.username if payment.created_by else "النظام",
            "amount": payment.amount,
        })
    return sorted(rows, key=lambda row: row["date"], reverse=True)


def monthly_financial_report(school, period_end=None):
    period_end = normalize_period_end(period_end)
    period_start, _ = financial_period(period_end)
    income_rows = _income_rows(school, period_start, period_end)
    expense_rows = list(ExpenseEntry.objects.filter(
        school=school,
        is_deleted=False,
        expense_date__range=(period_start, period_end),
    ).select_related("created_by"))
    canteen_rows = list(CanteenTransaction.objects.filter(
        school=school,
        is_deleted=False,
        transaction_date__range=(period_start, period_end),
    ).select_related("created_by"))
    target = MonthlyFinancialTarget.objects.filter(school=school, period_end=period_end).first()
    income = sum((row["amount"] for row in income_rows), ZERO)
    canteen_income = sum((row.amount for row in canteen_rows if row.transaction_type == "income"), ZERO)
    legacy_canteen_expenses = sum((row.amount for row in canteen_rows if row.transaction_type == "expense"), ZERO)
    school_expenses = sum((row.amount for row in expense_rows if row.source == "school"), ZERO)
    canteen_expenses = sum((row.amount for row in expense_rows if row.source == "canteen"), ZERO) + legacy_canteen_expenses
    expenses = school_expenses + canteen_expenses
    total_income = income + canteen_income
    expected = target.expected_amount if target else ZERO
    due = sum((invoice.remaining for invoice in StudentInvoice.objects.filter(
        academic_year__school=school,
        due_date__lte=period_end,
    ).exclude(status="cancelled")
        .exclude(carry_forward_record__source_invoices__isnull=False)
        .distinct()
        .prefetch_related("payments")), ZERO)
    method_totals = {}
    for row in income_rows:
        method_totals[row["method"]] = method_totals.get(row["method"], ZERO) + row["amount"]
    previous_end = period_start - timedelta(days=1)
    previous_statement = MonthlyFinancialStatement.objects.filter(school=school, period_end=previous_end).first()
    opening_balance = previous_statement.closing_balance if previous_statement else ZERO
    net_movement = total_income - expenses
    closing_balance = opening_balance + net_movement
    statement, _ = MonthlyFinancialStatement.objects.get_or_create(
        school=school,
        period_end=period_end,
        defaults={"opening_balance": opening_balance},
    )
    if not statement.is_closed:
        statement.opening_balance = opening_balance
        statement.fee_income = income
        statement.canteen_income = canteen_income
        statement.school_expenses = school_expenses
        statement.canteen_expenses = canteen_expenses
        statement.net_movement = net_movement
        statement.closing_balance = closing_balance
        statement.save()
    return {
        "period_start": period_start,
        "period_end": period_end,
        "income_rows": income_rows,
        "expense_rows": expense_rows,
        "income": total_income,
        "fee_income": income,
        "canteen_income": canteen_income,
        "expenses": expenses,
        "school_expenses": school_expenses,
        "canteen_expenses": canteen_expenses,
        "canteen_rows": canteen_rows,
        "canteen_profit": canteen_income - canteen_expenses,
        "opening_balance": statement.opening_balance,
        "net": statement.net_movement,
        "closing_balance": statement.closing_balance,
        "statement": statement,
        "expected": expected,
        "target": target,
        "target_difference": expected - total_income,
        "collection_rate": (total_income / expected * 100) if expected > 0 else ZERO,
        "due": due,
        "method_totals": sorted(method_totals.items()),
    }


@transaction.atomic
def close_monthly_statement(*, school, period_end, user):
    period_end = normalize_period_end(period_end)
    report = monthly_financial_report(school, period_end)
    statement = MonthlyFinancialStatement.objects.select_for_update().get(pk=report["statement"].pk)
    if timezone.localdate() < period_end:
        raise ValidationError("لا يمكن إغلاق الشهر قبل آخر يوم فعلي منه.")
    if not statement.is_closed:
        statement.is_closed = True
        statement.closed_by = user
        statement.closed_at = timezone.now()
        statement.save(update_fields=["is_closed", "closed_by", "closed_at", "updated_at"])
    return statement


def finance_consolidation_audit():
    """Read-only dependency audit before retiring legacy fee helpers."""
    from .models import DiscountRequest, Installment
    categories = []
    for category in FeeCategory.objects.annotate(invoice_count=Count("studentinvoice")):
        categories.append({
            "item": category,
            "invoice_count": category.invoice_count,
            "can_remove": category.invoice_count == 0,
        })
    discounts = {
        "total": DiscountRequest.objects.count(),
        "pending": DiscountRequest.objects.filter(status="pending").count(),
        "approved": DiscountRequest.objects.filter(status="approved").count(),
        "can_remove": not DiscountRequest.objects.exists(),
    }
    installments = {
        "total": Installment.objects.count(),
        "active": Installment.objects.exclude(status__in=["paid", "cancelled"]).count(),
        "can_remove": not Installment.objects.exists(),
    }
    return {
        "categories": categories,
        "discounts": discounts,
        "installments": installments,
        "safe_to_remove_all": all(row["can_remove"] for row in categories) and discounts["can_remove"] and installments["can_remove"],
    }


def next_expense_number():
    return f"EXP-{timezone.localdate().year}-{uuid.uuid4().hex[:8].upper()}"


@transaction.atomic
def close_financial_year(*, school, source_year, target_year, user, notes=""):
    source_year = AcademicYear.objects.select_for_update().get(pk=source_year.pk)
    target_year = AcademicYear.objects.select_for_update().get(pk=target_year.pk)
    if source_year.school_id != school.pk or target_year.school_id != school.pk:
        raise ValidationError("العامان يجب أن يتبعا المدرسة الحالية.")
    if source_year.pk == target_year.pk:
        raise ValidationError("اختر عامًا جديدًا لترحيل الأرصدة إليه.")
    if not source_year.is_closed:
        raise ValidationError("أغلق العام الدراسي أولًا قبل الإغلاق المالي.")
    if target_year.is_closed:
        raise ValidationError("لا يمكن الترحيل إلى عام مغلق.")
    if FinancialYearClosure.objects.filter(source_year=source_year).exists():
        raise ValidationError("تم إغلاق هذا العام ماليًا مسبقًا.")

    invoices = list(StudentInvoice.objects.select_for_update().filter(
        academic_year=source_year,
    ).exclude(status="cancelled").select_related("student").prefetch_related("payments"))
    balances = {}
    for invoice in invoices:
        if invoice.remaining > 0:
            balances[invoice.student_id] = balances.get(invoice.student_id, ZERO) + invoice.remaining

    closure = FinancialYearClosure.objects.create(
        school=school,
        source_year=source_year,
        target_year=target_year,
        total_carried=sum(balances.values(), ZERO),
        notes=(notes or "").strip(),
        closed_by=user,
    )
    source_by_student = {}
    for invoice in invoices:
        if invoice.student_id in balances:
            source_by_student.setdefault(invoice.student_id, []).append(invoice)
    for student_id, amount in balances.items():
        carried = FinancialCarryForward.objects.create(
            closure=closure,
            student_id=student_id,
            amount=amount,
        )
        carried.source_invoices.add(*source_by_student[student_id])
    return closure


def collection_dashboard(school):
    report = monthly_financial_report(school)
    academic_year = current_academic_year(school=school)
    money_field = DecimalField(max_digits=14, decimal_places=2)
    invoices = []
    if academic_year is not None:
        invoices = list(
            StudentInvoice.objects
            .filter(academic_year=academic_year)
            .exclude(status="cancelled")
            .exclude(carry_forward_record__source_invoices__isnull=False)
            .distinct()
            .select_related("student")
            .annotate(
                posted_paid=Coalesce(
                    Sum("payments__amount", filter=Q(payments__status="posted")),
                    Value(ZERO, output_field=money_field),
                )
            )
        )
    balances = {}
    overdue = ZERO
    current_fees = ZERO
    current_paid = ZERO
    today = timezone.localdate()
    for invoice in invoices:
        net_amount = max((invoice.amount or ZERO) - (invoice.discount_amount or ZERO), ZERO)
        paid_amount = min(max(invoice.posted_paid or ZERO, ZERO), net_amount)
        remaining = max(net_amount - paid_amount, ZERO)
        current_fees += net_amount
        current_paid += paid_amount
        if remaining > 0:
            balances[invoice.student_id] = {
                "student": invoice.student,
                "remaining": balances.get(invoice.student_id, {}).get("remaining", ZERO) + remaining,
            }
            if invoice.due_date < today:
                overdue += remaining
    debtors = sorted(balances.values(), key=lambda row: row["remaining"], reverse=True)
    current_remaining = sum((row["remaining"] for row in debtors), ZERO)
    from .previous_debt_services import previous_debt_summary

    previous = (
        previous_debt_summary(school=school, academic_year=academic_year)
        if academic_year is not None
        else {"total": ZERO, "guardians_count": 0, "students_count": 0}
    )
    return {
        **report,
        "current_year": academic_year,
        "current_fees": current_fees,
        "current_paid": current_paid,
        "current_remaining": current_remaining,
        "current_collection_rate": (
            current_paid / current_fees * 100 if current_fees > ZERO else ZERO
        ),
        "previous_remaining": previous["total"],
        "combined_remaining": current_remaining + previous["total"],
        "previous_guardians_count": previous["guardians_count"],
        "previous_students_count": previous["students_count"],
        # Compatibility aliases now deliberately mean current-year balances.
        "receivables": current_remaining,
        "overdue": overdue,
        "debtors": debtors[:20],
        "debtors_count": len(debtors),
    }
