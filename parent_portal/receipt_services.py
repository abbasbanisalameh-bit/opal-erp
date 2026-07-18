from __future__ import annotations

from decimal import Decimal

from django.db.models import Prefetch

from accounting.models import Receipt
from admissions.models import FeePayment, FeePaymentAllocation, StudentRegistration


def _receiver_details(user):
    if user is None:
        return "النظام", ""
    profile = getattr(user, "profile", None)
    name = (
        getattr(profile, "full_name", "")
        or user.get_full_name()
        or user.get_username()
        or "النظام"
    )
    role = getattr(getattr(profile, "role", None), "name", "")
    return name, role


def _row(
    *,
    receipt_number,
    created_at,
    amount,
    payment_type,
    allocations,
    created_by=None,
    status_label="معتمد",
):
    receiver, receiver_title = _receiver_details(created_by)
    allocations = [item for item in allocations if Decimal(item["amount"] or 0) > 0]
    return {
        "receipt_number": receipt_number or "-",
        "created_at": created_at,
        "amount": Decimal(amount or 0),
        "payment_type": payment_type,
        "payment_method": "-",
        "allocations": allocations,
        "children_names": "، ".join(item["student_name"] for item in allocations) or "-",
        "receiver": receiver,
        "receiver_title": receiver_title,
        "status_label": status_label,
    }


def build_guardian_receipt_history(students):
    """Return every receipt for authorized children as one read-only timeline.

    The three supported sources are canonical fee payments, registration receipts,
    and older accounting receipts. Registration receipts are excluded from the
    older source so the same receipt is never displayed twice.
    """
    student_ids = sorted({student.pk for student in students if getattr(student, "pk", None)})
    if not student_ids:
        return []

    history = []
    allocation_qs = FeePaymentAllocation.objects.filter(
        student_id__in=student_ids
    ).select_related("student")
    fee_payments = (
        FeePayment.objects.filter(allocations__student_id__in=student_ids, is_deleted=False)
        .select_related("created_by", "created_by__profile", "created_by__profile__role")
        .prefetch_related(
            Prefetch("allocations", queryset=allocation_qs, to_attr="guardian_allocations")
        )
        .distinct()
    )
    for payment in fee_payments:
        allocations = [
            {"student_name": item.student.full_name, "amount": item.amount}
            for item in payment.guardian_allocations
        ]
        history.append(
            _row(
                receipt_number=payment.receipt_number,
                created_at=payment.created_at,
                amount=payment.total_amount,
                payment_type=(
                    "تسديد رسوم لجميع الأبناء"
                    if payment.scope == "all_siblings"
                    else "تسديد رسوم طالب"
                ),
                allocations=allocations,
                created_by=payment.created_by,
            )
        )
        history[-1]["payment_method"] = payment.get_payment_method_display()

    registrations = list(
        StudentRegistration.objects.filter(
            student_id__in=student_ids,
            receipt__isnull=False,
            first_payment__gt=0,
            payment__status="posted",
        ).select_related(
            "student",
            "receipt",
            "created_by",
            "created_by__profile",
            "created_by__profile__role",
        )
    )
    registration_receipt_ids = [item.receipt_id for item in registrations]
    for registration in registrations:
        history.append(
            _row(
                receipt_number=registration.receipt.receipt_number,
                created_at=registration.receipt.created_at,
                amount=registration.first_payment,
                payment_type="دفعة التسجيل الأولى",
                allocations=[
                    {
                        "student_name": registration.student.full_name,
                        "amount": registration.first_payment,
                    }
                ],
                created_by=registration.created_by,
                status_label="ملغى" if registration.receipt.is_void else "معتمد",
            )
        )
        history[-1]["payment_method"] = registration.get_payment_method_display()

    older_receipts = (
        Receipt.objects.filter(payment__invoice__student_id__in=student_ids, payment__status="posted")
        .exclude(pk__in=registration_receipt_ids)
        .select_related(
            "payment",
            "payment__invoice",
            "payment__invoice__student",
            "payment__created_by",
            "payment__created_by__profile",
            "payment__created_by__profile__role",
        )
    )
    for receipt in older_receipts:
        payment = receipt.payment
        student = payment.invoice.student
        history.append(
            _row(
                receipt_number=receipt.receipt_number,
                created_at=receipt.created_at,
                amount=payment.amount,
                payment_type="إيصال رسوم سابق",
                allocations=[{"student_name": student.full_name, "amount": payment.amount}],
                created_by=payment.created_by,
                status_label="ملغى" if receipt.is_void else "معتمد",
            )
        )
        history[-1]["payment_method"] = payment.get_payment_method_display()

    return sorted(history, key=lambda item: item["created_at"], reverse=True)
