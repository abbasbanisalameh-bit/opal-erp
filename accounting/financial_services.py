from __future__ import annotations

import calendar
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from admissions.models import FeePayment, StudentRegistration
from core.models import AcademicYear

from .models import (
    ExpenseEntry,
    FeeCategory,
    FinancialCarryForward,
    FinancialYearClosure,
    MonthlyFinancialTarget,
    Receipt,
    StudentInvoice,
    StudentPayment,
)


ZERO = Decimal("0.00")


def financial_period(reference=None):
    """Return the inclusive school finance cycle: day 29 through day 28."""
    reference = reference or timezone.localdate()
    if reference.day <= 28:
        period_end = reference.replace(day=28)
    else:
        year = reference.year + (1 if reference.month == 12 else 0)
        month = 1 if reference.month == 12 else reference.month + 1
        period_end = date(year, month, 28)
    previous_day = period_end.replace(day=1) - timedelta(days=1)
    period_start = previous_day.replace(day=29)
    return period_start, period_end


def normalize_period_end(value=None):
    if not value:
        return financial_period()[1]
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError as exc:
            raise ValidationError("تاريخ الشهر المالي غير صحيح.") from exc
    if value.day != 28:
        raise ValidationError("اختر يوم 28 كنهاية للشهر المالي.")
    return value


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
            "description": item.get_scope_display(),
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
    target = MonthlyFinancialTarget.objects.filter(school=school, period_end=period_end).first()
    income = sum((row["amount"] for row in income_rows), ZERO)
    expenses = sum((row.amount for row in expense_rows), ZERO)
    expected = target.expected_amount if target else ZERO
    due = sum((invoice.remaining for invoice in StudentInvoice.objects.filter(
        academic_year__school=school,
        due_date__lte=period_end,
    ).exclude(status="cancelled").prefetch_related("payments")), ZERO)
    method_totals = {}
    for row in income_rows:
        method_totals[row["method"]] = method_totals.get(row["method"], ZERO) + row["amount"]
    return {
        "period_start": period_start,
        "period_end": period_end,
        "income_rows": income_rows,
        "expense_rows": expense_rows,
        "income": income,
        "expenses": expenses,
        "net": income - expenses,
        "expected": expected,
        "target": target,
        "target_difference": expected - income,
        "collection_rate": (income / expected * 100) if expected > 0 else ZERO,
        "due": due,
        "method_totals": sorted(method_totals.items()),
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
    category, _ = FeeCategory.objects.get_or_create(
        name=f"رصيد مرحل من {source_year.name}",
        defaults={"description": "رصيد مالي مرحل بعد إغلاق العام", "amount": 0, "active": True},
    )
    source_by_student = {}
    for invoice in invoices:
        if invoice.student_id in balances:
            source_by_student.setdefault(invoice.student_id, []).append(invoice)
    for student_id, amount in balances.items():
        target_invoice = StudentInvoice.objects.create(
            student_id=student_id,
            academic_year=target_year,
            fee_category=category,
            amount=amount,
            due_date=target_year.start_date,
            notes=f"رصيد مرحل آليًا من العام {source_year.name}",
            created_by=user,
        )
        FinancialCarryForward.objects.create(
            closure=closure,
            student_id=student_id,
            amount=amount,
            target_invoice=target_invoice,
        )
        for invoice in source_by_student[student_id]:
            invoice.status = "cancelled"
            invoice.paid = False
            invoice.cancelled_by = user
            invoice.cancelled_at = timezone.now()
            invoice.cancellation_reason = f"أُغلق ماليًا ورُحّل الرصيد إلى {target_year.name}"
            invoice.save(update_fields=["status", "paid", "cancelled_by", "cancelled_at", "cancellation_reason", "updated_at"])
    return closure


def collection_dashboard(school):
    report = monthly_financial_report(school)
    invoices = list(StudentInvoice.objects.filter(academic_year__school=school).exclude(status="cancelled").select_related("student").prefetch_related("payments"))
    balances = {}
    overdue = ZERO
    for invoice in invoices:
        if invoice.remaining > 0:
            balances[invoice.student_id] = {
                "student": invoice.student,
                "remaining": balances.get(invoice.student_id, {}).get("remaining", ZERO) + invoice.remaining,
            }
            if invoice.is_overdue:
                overdue += invoice.remaining
    debtors = sorted(balances.values(), key=lambda row: row["remaining"], reverse=True)
    return {**report, "receivables": sum((row["remaining"] for row in debtors), ZERO), "overdue": overdue, "debtors": debtors[:20], "debtors_count": len(debtors)}
