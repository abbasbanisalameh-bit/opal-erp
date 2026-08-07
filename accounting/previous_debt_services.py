"""Canonical previous-year debt services for OPAL school finance.

Previous debt is never stored in a parallel balance table.  It is derived from
non-cancelled StudentInvoice rows belonging to academic years older than the
current year, minus posted StudentPayment rows on those same invoices.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from academics.models import Enrollment
from admissions.models import (
    LEGACY_PREVIOUS_YEARS_FEE_NOTE_PREFIXES,
    PREVIOUS_YEARS_FEE_NOTE_PREFIX,
    FeePayment,
    FeePaymentAllocation,
    StudentRegistration,
)
from core.academic_context import current_academic_year
from core.finance_constants import ACTIVE_PAYMENT_METHOD_CHOICES
from parent_portal.models import FamilyStudent

from .models import FinancialCarryForward, StudentInvoice, StudentPayment

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
MONEY_FIELD = DecimalField(max_digits=14, decimal_places=2)
PREVIOUS_DEBT_NOTE_PREFIX = PREVIOUS_YEARS_FEE_NOTE_PREFIX
LEGACY_PREVIOUS_DEBT_NOTE_PREFIXES = LEGACY_PREVIOUS_YEARS_FEE_NOTE_PREFIXES


def money(value) -> Decimal:
    return Decimal(value or 0).quantize(CENT, rounding=ROUND_HALF_UP)


def resolve_current_year_for_student(student, academic_year=None):
    if academic_year is not None:
        return academic_year
    school = getattr(student, "school", None)
    if school is None:
        enrollment = (
            student.enrollments.select_related("academic_year__school")
            .order_by("-academic_year__start_date", "-pk")
            .first()
        )
        school = enrollment.academic_year.school if enrollment and enrollment.academic_year_id else None
    if school is None:
        invoice = (
            student.invoices.filter(academic_year__isnull=False)
            .select_related("academic_year__school")
            .order_by("-academic_year__start_date", "-pk")
            .first()
        )
        school = invoice.academic_year.school if invoice and invoice.academic_year_id else None
    return current_academic_year(school=school) if school else None


def _previous_invoice_queryset(*, student=None, school=None, academic_year=None):
    current_year = academic_year
    if current_year is None and student is not None:
        current_year = resolve_current_year_for_student(student)
    if current_year is None and school is not None:
        current_year = current_academic_year(school=school)

    qs = (
        StudentInvoice.objects.exclude(status="cancelled")
        .filter(academic_year__isnull=False)
        # Older OPAL versions could keep a compatibility target invoice while
        # also linking the real source invoices to the carry-forward record.
        # The source invoices are authoritative; excluding that duplicate
        # target prevents the same previous debt from being counted twice.
        .exclude(carry_forward_record__source_invoices__isnull=False)
        .distinct()
    )
    if student is not None:
        qs = qs.filter(student=student)
    if school is not None:
        qs = qs.filter(academic_year__school=school)
    elif current_year is not None:
        qs = qs.filter(academic_year__school=current_year.school)
    if current_year is None:
        return qs.none(), None

    qs = qs.filter(academic_year__start_date__lt=current_year.start_date)
    return (
        qs.select_related("student", "academic_year", "fee_category")
        .annotate(
            posted_total=Coalesce(
                Sum("payments__amount", filter=Q(payments__status="posted")),
                Value(ZERO, output_field=MONEY_FIELD),
                output_field=MONEY_FIELD,
            )
        )
        .order_by("academic_year__start_date", "due_date", "pk"),
        current_year,
    )


def _grade_map(student, year_ids):
    mapping = {}
    enrollments = (
        Enrollment.objects.filter(student=student, academic_year_id__in=year_ids)
        .select_related("grade", "section")
        .order_by("academic_year__start_date", "pk")
    )
    for enrollment in enrollments:
        mapping.setdefault(
            enrollment.academic_year_id,
            {
                "grade": enrollment.grade,
                "section": enrollment.section,
                "grade_label": str(enrollment.grade) if enrollment.grade_id else "غير محدد",
                "section_label": str(enrollment.section) if enrollment.section_id else "",
            },
        )

    missing = set(year_ids) - set(mapping)
    if missing:
        registrations = (
            StudentRegistration.objects.filter(student=student, academic_year_id__in=missing)
            .select_related("grade", "section")
            .order_by("academic_year__start_date", "pk")
        )
        for registration in registrations:
            mapping.setdefault(
                registration.academic_year_id,
                {
                    "grade": registration.grade,
                    "section": registration.section,
                    "grade_label": str(registration.grade) if registration.grade_id else "غير محدد",
                    "section_label": str(registration.section) if registration.section_id else "",
                },
            )
    return mapping


def student_previous_debt_snapshot(student, *, academic_year=None):
    invoices_qs, current_year = _previous_invoice_queryset(student=student, academic_year=academic_year)
    invoices = list(invoices_qs)
    grade_map = _grade_map(student, {invoice.academic_year_id for invoice in invoices})
    years = defaultdict(lambda: {"invoices": [], "total": ZERO})
    total = ZERO

    for invoice in invoices:
        net = money(invoice.amount - invoice.discount_amount)
        paid = money(invoice.posted_total)
        remaining = money(max(net - paid, ZERO))
        if remaining <= ZERO:
            continue
        grade_info = grade_map.get(invoice.academic_year_id, {})
        row = {
            "invoice": invoice,
            "academic_year": invoice.academic_year,
            "grade": grade_info.get("grade"),
            "section": grade_info.get("section"),
            "grade_label": grade_info.get("grade_label", "غير محدد"),
            "section_label": grade_info.get("section_label", ""),
            "net": net,
            "paid": paid,
            "remaining": remaining,
        }
        bucket = years[invoice.academic_year_id]
        bucket["academic_year"] = invoice.academic_year
        bucket["grade"] = row["grade"]
        bucket["section"] = row["section"]
        bucket["grade_label"] = row["grade_label"]
        bucket["section_label"] = row["section_label"]
        bucket["invoices"].append(row)
        bucket["total"] = money(bucket["total"] + remaining)
        total = money(total + remaining)

    rows = sorted(years.values(), key=lambda item: (item["academic_year"].start_date, item["academic_year"].pk))
    years_text = "، ".join(
        f"{row['academic_year'].name} — {row['grade_label']}"
        + (f" / {row['section_label']}" if row["section_label"] else "")
        for row in rows
    )
    return {
        "student": student,
        "current_year": current_year,
        "has_debt": total > ZERO,
        "total": total,
        "rows": rows,
        "years_text": years_text,
    }


def _guardian_link_map(student_ids):
    return {
        link.student_id: link.family
        for link in FamilyStudent.objects.filter(student_id__in=student_ids, is_active=True)
        .select_related("family")
    }


def previous_debt_summary(*, school, academic_year=None):
    """Return lightweight totals for the manager dashboard.

    The dashboard needs only the total outstanding amount and distinct guardian
    and student counts.  Building the full guardian/receipt report on every
    page load is unnecessarily expensive, so this function reads the canonical
    invoice balances once and resolves only the active family links needed for
    the counters.
    """
    invoices_qs, current_year = _previous_invoice_queryset(
        school=school,
        academic_year=academic_year,
    )
    if current_year is None:
        return {
            "school": school,
            "current_year": None,
            "total": ZERO,
            "guardians_count": 0,
            "students_count": 0,
        }

    outstanding_by_student = defaultdict(lambda: ZERO)
    for invoice in invoices_qs.select_related(None).only(
        "id",
        "student_id",
        "amount",
        "discount_amount",
        "academic_year_id",
    ):
        net = money(invoice.amount - invoice.discount_amount)
        remaining = money(max(net - money(invoice.posted_total), ZERO))
        if remaining > ZERO:
            outstanding_by_student[invoice.student_id] = money(
                outstanding_by_student[invoice.student_id] + remaining
            )

    student_ids = set(outstanding_by_student)
    family_links = list(
        FamilyStudent.objects.filter(student_id__in=student_ids, is_active=True)
        .values_list("student_id", "family_id")
    )
    family_ids = {family_id for _student_id, family_id in family_links}
    linked_student_ids = {student_id for student_id, _family_id in family_links}
    unlinked_students_count = len(student_ids - linked_student_ids)

    return {
        "school": school,
        "current_year": current_year,
        "total": money(sum(outstanding_by_student.values(), ZERO)),
        "guardians_count": len(family_ids) + unlinked_students_count,
        "students_count": len(student_ids),
    }

def previous_debt_guardian_report(*, school, academic_year=None):
    invoices_qs, current_year = _previous_invoice_queryset(school=school, academic_year=academic_year)
    invoices = list(invoices_qs)
    student_ids = {invoice.student_id for invoice in invoices}
    families = _guardian_link_map(student_ids)

    student_invoice_rows = defaultdict(list)
    year_ids_by_student = defaultdict(set)
    for invoice in invoices:
        net = money(invoice.amount - invoice.discount_amount)
        paid = money(invoice.posted_total)
        remaining = money(max(net - paid, ZERO))
        if remaining <= ZERO:
            continue
        student_invoice_rows[invoice.student_id].append((invoice, net, paid, remaining))
        year_ids_by_student[invoice.student_id].add(invoice.academic_year_id)

    grade_maps = {
        student_id: _grade_map(rows[0][0].student, year_ids_by_student[student_id])
        for student_id, rows in student_invoice_rows.items()
    }
    grouped = {}
    for student_id, rows in student_invoice_rows.items():
        student = rows[0][0].student
        family = families.get(student_id)
        key = ("family", family.pk) if family else ("student", student_id)
        group = grouped.setdefault(
            key,
            {
                "family": family,
                "guardian_name": family.guardian_name if family else (student.guardian_name or "غير مرتبط بملف ولي أمر"),
                "phone": family.phone if family else (student.phone or ""),
                "children": [],
                "receipts": [],
                "total": ZERO,
            },
        )
        year_groups = defaultdict(lambda: {"invoices": [], "total": ZERO})
        for invoice, net, paid, remaining in rows:
            grade_info = grade_maps[student_id].get(invoice.academic_year_id, {})
            year_group = year_groups[invoice.academic_year_id]
            year_group.update(
                {
                    "academic_year": invoice.academic_year,
                    "grade_label": grade_info.get("grade_label", "غير محدد"),
                    "section_label": grade_info.get("section_label", ""),
                }
            )
            year_group["invoices"].append(
                {"invoice": invoice, "net": net, "paid": paid, "remaining": remaining}
            )
            year_group["total"] = money(year_group["total"] + remaining)
        child_total = money(sum((item["total"] for item in year_groups.values()), ZERO))
        group["children"].append(
            {
                "student": student,
                "years": sorted(year_groups.values(), key=lambda item: item["academic_year"].start_date),
                "total": child_total,
            }
        )
        group["total"] = money(group["total"] + child_total)

    if grouped:
        original_due_by_guardian = defaultdict(lambda: ZERO)
        for invoice in invoices:
            family = families.get(invoice.student_id)
            guardian_key = ("family", family.pk) if family else ("student", invoice.student_id)
            if guardian_key in grouped:
                original_due_by_guardian[guardian_key] = money(
                    original_due_by_guardian[guardian_key]
                    + max(money(invoice.amount - invoice.discount_amount), ZERO)
                )

        report_student_ids = {
            invoice.student_id
            for invoice in invoices
            if (("family", families[invoice.student_id].pk) if families.get(invoice.student_id) else ("student", invoice.student_id)) in grouped
        }
        old_payments = list(
            StudentPayment.objects.filter(
                status="posted",
                invoice__student_id__in=report_student_ids,
                invoice__academic_year__start_date__lt=current_year.start_date,
                invoice__academic_year__school=school,
            )
            .exclude(invoice__status="cancelled")
            .select_related("invoice__student", "invoice__academic_year")
            .order_by("payment_date", "created_at", "pk")
        )
        receipt_numbers = {payment.reference for payment in old_payments if payment.reference}
        fee_receipts = {
            item.receipt_number: item
            for item in FeePayment.objects.filter(receipt_number__in=receipt_numbers, is_deleted=False)
        }
        receipt_groups = {}
        for payment in old_payments:
            family = families.get(payment.invoice.student_id)
            guardian_key = ("family", family.pk) if family else ("student", payment.invoice.student_id)
            if guardian_key not in grouped:
                continue
            receipt_key = payment.reference or f"OLD-{payment.pk}"
            key = (guardian_key, receipt_key)
            row = receipt_groups.setdefault(
                key,
                {
                    "receipt_number": receipt_key,
                    "amount": ZERO,
                    "payments": [],
                    "created_at": payment.created_at,
                    "payment_date": payment.payment_date,
                    "fee_payment": fee_receipts.get(receipt_key),
                },
            )
            row["amount"] = money(row["amount"] + payment.amount)
            row["payments"].append(payment)
            if payment.created_at < row["created_at"]:
                row["created_at"] = payment.created_at
            if payment.payment_date < row["payment_date"]:
                row["payment_date"] = payment.payment_date

        cumulative_by_guardian = defaultdict(lambda: ZERO)
        for (guardian_key, _receipt_key), receipt in receipt_groups.items():
            cumulative_by_guardian[guardian_key] = money(
                cumulative_by_guardian[guardian_key] + receipt["amount"]
            )
            receipt["remaining_after"] = money(
                max(original_due_by_guardian[guardian_key] - cumulative_by_guardian[guardian_key], ZERO)
            )
            grouped[guardian_key]["receipts"].append(receipt)

    rows = sorted(grouped.values(), key=lambda item: (-item["total"], item["guardian_name"]))
    for row in rows:
        row["children"].sort(key=lambda child: child["student"].full_name)
        row["receipts"].sort(key=lambda receipt: receipt["created_at"], reverse=True)
    return {
        "school": school,
        "current_year": current_year,
        "total": money(sum((row["total"] for row in rows), ZERO)),
        "guardians_count": len(rows),
        "students_count": len(student_invoice_rows),
        "rows": rows,
    }


def sync_carry_forward_status_for_invoices(invoice_ids):
    """Synchronize compatibility carry-forward status from real invoice balances."""
    invoice_ids = {pk for pk in invoice_ids if pk}
    if not invoice_ids:
        return
    carry_rows = FinancialCarryForward.objects.filter(
        Q(source_invoices__pk__in=invoice_ids) | Q(target_invoice_id__in=invoice_ids)
    ).distinct()
    for carry in carry_rows.prefetch_related("source_invoices__payments"):
        new_status = "settled" if carry.remaining <= ZERO else "open"
        if carry.status != new_status:
            FinancialCarryForward.objects.filter(pk=carry.pk).update(status=new_status)


def previous_debt_receipt_breakdown(fee_payment):
    allocations = list(
        fee_payment.allocations.select_related(
            "student", "invoice", "invoice__academic_year", "invoice__fee_category"
        ).order_by("invoice__academic_year__start_date", "invoice__due_date", "pk")
    )
    if not allocations:
        return {"is_previous_debt": False, "rows": []}
    old_allocations = [
        allocation
        for allocation in allocations
        if allocation.invoice_id and allocation.invoice.academic_year_id
    ]
    # The receipt must preserve its original identity after academic years
    # advance.  The durable note prefix is written only by the dedicated
    # previous-debt payment service; relying on today's current year would
    # incorrectly relabel ordinary historical receipts later.
    is_previous = (
        any(
            (fee_payment.notes or "").startswith(prefix)
            for prefix in (PREVIOUS_DEBT_NOTE_PREFIX, *LEGACY_PREVIOUS_DEBT_NOTE_PREFIXES)
        )
        and bool(old_allocations)
        and len(old_allocations) == len(allocations)
    )
    if not is_previous:
        return {"is_previous_debt": False, "rows": []}

    year_ids_by_student = defaultdict(set)
    students = {}
    for allocation in old_allocations:
        year_ids_by_student[allocation.student_id].add(allocation.invoice.academic_year_id)
        students[allocation.student_id] = allocation.student
    grade_maps = {
        student_id: _grade_map(students[student_id], year_ids)
        for student_id, year_ids in year_ids_by_student.items()
    }
    rows = []
    for allocation in old_allocations:
        grade_info = grade_maps[allocation.student_id].get(allocation.invoice.academic_year_id, {})
        rows.append(
            {
                "allocation": allocation,
                "student": allocation.student,
                "invoice": allocation.invoice,
                "academic_year": allocation.invoice.academic_year,
                "grade_label": grade_info.get("grade_label", "غير محدد"),
                "section_label": grade_info.get("section_label", ""),
                "category": allocation.invoice.fee_category,
                "remaining_before": allocation.remaining_before,
                "amount": allocation.amount,
                "remaining_after": allocation.remaining_after,
            }
        )
    return {"is_previous_debt": True, "rows": rows}


@transaction.atomic
def create_previous_debt_payment(
    *, student, amount, user, payment_method, operation_token, notes="", academic_year=None
):
    try:
        amount = money(amount)
    except (ArithmeticError, ValueError):
        raise ValidationError("أدخل مبلغ دفعة صحيحًا.") from None
    if amount <= ZERO:
        raise ValidationError("يجب أن يكون مبلغ الدفعة أكبر من صفر.")
    if payment_method not in {value for value, _label in ACTIVE_PAYMENT_METHOD_CHOICES}:
        raise ValidationError("اختر طريقة دفع صحيحة.")

    existing = FeePayment.objects.filter(operation_token=operation_token).first()
    if existing:
        return existing

    current_year = resolve_current_year_for_student(student, academic_year=academic_year)
    if current_year is None:
        raise ValidationError("لا يوجد عام دراسي حالي لتحديد متبقيات الرسوم السابقة.")

    invoices_qs, _ = _previous_invoice_queryset(student=student, academic_year=current_year)
    invoices = list(invoices_qs.select_for_update())
    payable = []
    due_before = ZERO
    for invoice in invoices:
        net = money(invoice.amount - invoice.discount_amount)
        paid = money(invoice.posted_total)
        remaining = money(max(net - paid, ZERO))
        if remaining > ZERO:
            payable.append((invoice, net, paid, remaining))
            due_before = money(due_before + remaining)

    if due_before <= ZERO:
        raise ValidationError("لا توجد متبقيات رسوم سابقة على هذا الطالب.")
    if amount > due_before:
        raise ValidationError(f"المبلغ يتجاوز إجمالي متبقيات الرسوم السابقة ({due_before} د.أ).")

    from admissions.financial_services import generate_fee_payment_receipt_number

    family_link = student.family_links.filter(is_active=True).select_related("family").first()
    family = family_link.family if family_link else None
    fee_payment = FeePayment.objects.create(
        school=current_year.school,
        receipt_number=generate_fee_payment_receipt_number(),
        scope="single",
        main_student=student,
        guardian_name=(family.guardian_name if family else student.guardian_name) or "",
        phone=(family.phone if family else student.phone) or "",
        total_amount=amount,
        total_due_before=due_before,
        total_due_after=money(due_before - amount),
        payment_method=payment_method,
        operation_token=operation_token,
        created_by=user if getattr(user, "is_authenticated", False) else None,
        notes=(PREVIOUS_DEBT_NOTE_PREFIX + (f" — {(notes or '').strip()}" if (notes or "").strip() else "")),
    )

    left = amount
    touched_invoice_ids = []
    for invoice, net, paid_before, remaining_before in payable:
        if left <= ZERO:
            break
        allocated = min(left, remaining_before)
        accounting_payment = StudentPayment.objects.create(
            invoice=invoice,
            amount=allocated,
            payment_method=payment_method,
            reference=fee_payment.receipt_number,
            created_by=user if getattr(user, "is_authenticated", False) else None,
            notes=f"دفعة من متبقيات الرسوم السابقة عن العام {invoice.academic_year.name}",
        )
        FeePaymentAllocation.objects.create(
            fee_payment=fee_payment,
            student=student,
            invoice=invoice,
            accounting_payment=accounting_payment,
            amount=allocated,
            total_fees=net,
            paid_before=paid_before,
            remaining_before=remaining_before,
            remaining_after=money(remaining_before - allocated),
        )
        touched_invoice_ids.append(invoice.pk)
        left = money(left - allocated)

    if left > ZERO:
        raise ValidationError("تعذر توزيع مبلغ الدفعة كاملًا على متبقيات الرسوم السابقة.")

    sync_carry_forward_status_for_invoices(touched_invoice_ids)

    from parent_portal.notification_services import notify_guardian_for_student

    notify_guardian_for_student(
        student,
        "تسجيل دفعة من متبقيات الرسوم السابقة",
        f"تم تسجيل دفعة بقيمة {amount} د.أ من متبقيات الرسوم السابقة. رقم الإيصال {fee_payment.receipt_number}.",
        event_key=f"previous-debt-payment:{fee_payment.pk}",
        link="/parent/fees/",
    )
    return fee_payment
