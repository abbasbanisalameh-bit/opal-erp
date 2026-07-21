from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from accounting.models import FeeCategory, StudentInvoice, StudentPayment
from core.models import Sequence
from students.models import Student

from .models import FeePayment, FeePaymentAllocation
from .services import active_school

TWOPLACES = Decimal("0.01")


def money(value):
    return Decimal(value or 0).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def next_finance_sequence(key, prefix, padding=6):
    seq, _ = Sequence.objects.select_for_update().get_or_create(
        key=key,
        defaults={"prefix": prefix, "current_number": 0, "padding": padding, "yearly_reset": True},
    )
    seq.current_number += 1
    seq.padding = seq.padding or padding
    seq.save(update_fields=["current_number", "padding"])
    return f"{seq.prefix}{str(seq.current_number).zfill(seq.padding)}"


def generate_fee_payment_receipt_number():
    year = timezone.localdate().year
    return next_finance_sequence(f"fee_payment_receipt_{year}", f"PAY-{year}-", 6)


def _latest_registration(student):
    """Return the latest registration record without assuming an active-year flag."""
    return (
        student.registrations
        .select_related("academic_year", "invoice", "payment")
        .order_by("-created_at", "-pk")
        .first()
    )


def student_finance_snapshot(student):
    """Return the live balance from invoices and posted payments only."""
    invoice_total = sum((invoice.net_amount for invoice in student.invoices.exclude(status="cancelled")), Decimal("0.00"))
    accounting_paid = (
        StudentPayment.objects.filter(invoice__student=student, status="posted")
        .exclude(invoice__status="cancelled")
        .aggregate(total=models.Sum("amount"))["total"]
        or Decimal("0.00")
    )
    registration = _latest_registration(student)
    total = money(invoice_total)
    paid = money(min(accounting_paid, total)) if total > 0 else Decimal("0.00")
    remaining = money(max(total - paid, Decimal("0.00")))

    if total <= 0 or remaining <= 0:
        status = "paid"
    elif paid <= 0:
        status = "unpaid"
    else:
        status = "partial"

    return {
        "total": total,
        "paid": paid,
        "remaining": remaining,
        "status": status,
        "invoice_total": total,
        "accounting_paid": paid,
        "registration": registration,
    }


def student_total_fees(student):
    return student_finance_snapshot(student)["total"]


def student_total_paid(student):
    return student_finance_snapshot(student)["paid"]


def student_remaining(student):
    return student_finance_snapshot(student)["remaining"]


def student_payment_status(student):
    return student_finance_snapshot(student)["status"]


def find_sibling_students(student):
    """Return children of the one canonical Family record only.

    National/personal guardian identity is resolved when Family is created. We
    never infer siblings from similar names or shared phone numbers.
    """
    family_link = student.family_links.filter(is_active=True).select_related("family").first()
    if not family_link:
        return Student.objects.filter(pk=student.pk, is_active=True)
    linked_ids = family_link.family.children.filter(is_active=True).values_list("student_id", flat=True)
    return Student.objects.filter(pk__in=linked_ids, is_active=True).order_by("full_name")


def search_students(query):
    query = (query or "").strip()
    qs = Student.objects.filter(is_active=True).order_by("full_name")
    if not query:
        return qs.none()
    return qs.filter(
        models.Q(full_name__icontains=query)
        | models.Q(student_number__icontains=query)
        | models.Q(national_id__icontains=query)
        | models.Q(family_links__family__identity_number__icontains=query)
        | models.Q(phone__icontains=query)
        | models.Q(guardian_name__icontains=query)
        | models.Q(father_name__icontains=query)
    ).distinct()[:20]


def distribute_amount(rows, amount):
    """Distribute to outstanding balances only, evenly and to the nearest cent."""
    amount = money(amount)
    data = [{**row, "allocated": Decimal("0.00")} for row in rows]
    left = amount

    while left > 0:
        eligible = [row for row in data if money(row["remaining"] - row["allocated"]) > 0]
        if not eligible:
            break

        # Work in cents to prevent an endless loop caused by rounding.
        cents = int((left * 100).to_integral_value(rounding=ROUND_HALF_UP))
        base_cents, extra_cents = divmod(cents, len(eligible))
        progressed = False

        for index, row in enumerate(eligible):
            requested_cents = base_cents + (1 if index < extra_cents else 0)
            if requested_cents <= 0:
                continue
            requested = money(Decimal(requested_cents) / 100)
            capacity = money(row["remaining"] - row["allocated"])
            give = min(requested, capacity, left)
            if give > 0:
                row["allocated"] = money(row["allocated"] + give)
                left = money(left - give)
                progressed = True

        if not progressed:
            break

    return data, money(left)


def allocate_equally_to_unpaid_siblings(students, amount):
    rows = []
    for student in students:
        finance = student_finance_snapshot(student)
        rows.append({
            "student": student,
            "total": finance["total"],
            "paid": finance["paid"],
            "remaining": finance["remaining"],
        })
    return distribute_amount(rows, amount)



def build_family_payment_preview(main_student, amount):
    """Return a safe, read-only preview of automatic sibling allocation."""
    amount = money(amount)
    siblings = list(find_sibling_students(main_student))
    rows, unused_amount = allocate_equally_to_unpaid_siblings(siblings, amount)
    due_before = money(sum((row["remaining"] for row in rows), Decimal("0.00")))
    allocated_total = money(sum((row["allocated"] for row in rows), Decimal("0.00")))
    due_after = money(max(due_before - allocated_total, Decimal("0.00")))

    preview_rows = []
    for row in rows:
        remaining_after = money(max(row["remaining"] - row["allocated"], Decimal("0.00")))
        if remaining_after <= 0:
            status = "paid"
            status_label = "مسدد بالكامل"
        elif row["paid"] + row["allocated"] <= 0:
            status = "unpaid"
            status_label = "غير مسدد"
        else:
            status = "partial"
            status_label = "سداد جزئي"
        preview_rows.append({
            **row,
            "remaining_after": remaining_after,
            "status_after": status,
            "status_after_label": status_label,
        })

    return {
        "rows": preview_rows,
        "amount": amount,
        "allocated_total": allocated_total,
        "unused_amount": unused_amount,
        "due_before": due_before,
        "due_after": due_after,
        "is_valid": amount > 0 and due_before > 0 and unused_amount <= 0,
    }

def ensure_balance_invoice(student, minimum_amount):
    """Create an invoice for the uninvoiced obligation, never only for the payment."""
    snapshot = student_finance_snapshot(student)
    existing_invoice_total = snapshot["invoice_total"]
    uninvoiced_obligation = money(max(snapshot["total"] - existing_invoice_total, Decimal("0.00")))
    invoice_amount = max(money(minimum_amount), uninvoiced_obligation)
    category, _ = FeeCategory.objects.get_or_create(
        name="رصيد رسوم مدرسية",
        defaults={"description": "رصيد رسوم مرحّل للطالب", "amount": invoice_amount, "active": True},
    )
    enrollment = student.enrollments.filter(status="active").select_related("academic_year").order_by("-academic_year__start_date").first()
    return StudentInvoice.objects.create(
        student=student,
        academic_year=enrollment.academic_year if enrollment else None,
        fee_category=category,
        amount=invoice_amount,
        due_date=timezone.localdate(),
        paid=False,
    )


def apply_student_payment(student, amount, receipt_number, *, user=None, payment_method="unspecified"):
    """Apply one allocation across open invoices without overpaying any invoice."""
    left = money(amount)
    first_invoice = None
    first_payment = None

    open_invoices = list(student.invoices.exclude(status__in=["paid", "cancelled"]).order_by("due_date", "id"))
    for invoice in open_invoices:
        capacity = money(max(invoice.remaining, Decimal("0.00")))
        if capacity <= 0:
            invoice.sync_status()
            continue
        give = min(left, capacity)
        payment = StudentPayment.objects.create(
            invoice=invoice,
            amount=give,
            payment_method=payment_method,
            reference=receipt_number,
            created_by=user if getattr(user, "is_authenticated", False) else None,
            notes=f"دفعة عن جميع الإخوة - إيصال {receipt_number}",
        )
        first_invoice = first_invoice or invoice
        first_payment = first_payment or payment
        left = money(left - give)
        if left <= 0:
            break

    # Legacy balances may exist on students without invoices.
    if left > 0:
        invoice = ensure_balance_invoice(student, left)
        payment = StudentPayment.objects.create(
            invoice=invoice,
            amount=left,
            payment_method=payment_method,
            reference=receipt_number,
            created_by=user if getattr(user, "is_authenticated", False) else None,
            notes=f"دفعة عن جميع الإخوة - إيصال {receipt_number}",
        )
        first_invoice = first_invoice or invoice
        first_payment = first_payment or payment
        left = Decimal("0.00")

    return first_invoice, first_payment


@transaction.atomic
def create_siblings_fee_payment(*, main_student, amount, user, payment_method, operation_token, notes=""):
    amount = money(amount)
    if amount <= 0:
        raise ValidationError("يجب أن يكون مبلغ الدفعة أكبر من صفر.")
    if payment_method not in {"cash", "card", "bank_transfer", "online", "cheque"}:
        raise ValidationError("اختر طريقة دفع صحيحة.")
    existing = FeePayment.objects.filter(operation_token=operation_token).first()
    if existing:
        return existing

    school = active_school()
    siblings = list(find_sibling_students(main_student).select_for_update())
    allocations_data, unused_amount = allocate_equally_to_unpaid_siblings(siblings, amount)
    due_before = money(sum((row["remaining"] for row in allocations_data), Decimal("0.00")))

    if due_before <= 0:
        raise ValidationError("جميع أبناء ولي الأمر مسددون بالكامل.")
    if unused_amount > 0:
        raise ValidationError(f"المبلغ أكبر من إجمالي المتبقي على أبناء ولي الأمر بمقدار {unused_amount} د.أ.")

    total_allocated = money(sum((row["allocated"] for row in allocations_data), Decimal("0.00")))
    due_after = money(due_before - total_allocated)
    receipt_number = generate_fee_payment_receipt_number()

    has_unpaid_other_siblings = any(
        row["student"].pk != main_student.pk and row["remaining"] > 0
        for row in allocations_data
    )
    fee_payment = FeePayment.objects.create(
        school=school,
        receipt_number=receipt_number,
        scope="all_siblings" if has_unpaid_other_siblings else "single",
        main_student=main_student,
        guardian_name=main_student.guardian_name,
        phone=main_student.phone,
        total_amount=total_allocated,
        total_due_before=due_before,
        total_due_after=due_after,
        payment_method=payment_method,
        operation_token=operation_token,
        created_by=user if getattr(user, "is_authenticated", False) else None,
        notes=(notes or "").strip(),
    )

    for item in allocations_data:
        student = item["student"]
        allocated = money(item["allocated"])
        invoice = payment = None
        if allocated > 0:
            invoice, payment = apply_student_payment(student, allocated, receipt_number, user=user, payment_method=payment_method)

        FeePaymentAllocation.objects.create(
            fee_payment=fee_payment,
            student=student,
            invoice=invoice,
            accounting_payment=payment,
            amount=allocated,
            total_fees=item["total"],
            paid_before=item["paid"],
            remaining_before=item["remaining"],
            remaining_after=money(item["remaining"] - allocated),
        )

    from parent_portal.notification_services import notify_guardians_for_fee_payment
    notify_guardians_for_fee_payment(fee_payment)
    return fee_payment


@transaction.atomic
def safe_delete_fee_payment(*, fee_payment, user, reason):
    fee_payment = FeePayment.objects.select_for_update().get(pk=fee_payment.pk)
    if fee_payment.is_deleted:
        return False
    if not (reason or "").strip():
        raise ValidationError("اكتب سبب الحذف الآمن.")
    year_ids = fee_payment.allocations.values_list("invoice__academic_year_id", flat=True)
    from accounting.models import FinancialYearClosure
    if FinancialYearClosure.objects.filter(source_year_id__in=[pk for pk in year_ids if pk]).exists():
        raise ValidationError("لا يمكن حذف إيصال داخل عام مغلق ماليًا.")
    linked_ids = fee_payment.allocations.exclude(accounting_payment_id=None).values_list("accounting_payment_id", flat=True)
    payments = StudentPayment.objects.select_for_update().filter(
        models.Q(pk__in=linked_ids)
        | models.Q(reference=fee_payment.receipt_number)
        | models.Q(notes__icontains=fee_payment.receipt_number)
    ).distinct()
    for payment in payments:
        if payment.status == "posted":
            payment.safe_delete(user, reason)
    fee_payment.is_deleted = True
    fee_payment.deleted_by = user
    fee_payment.deleted_at = timezone.now()
    fee_payment.deletion_reason = reason.strip()
    fee_payment.save(update_fields=["is_deleted", "deleted_by", "deleted_at", "deletion_reason"])
    return True


@transaction.atomic
def safe_delete_registration_payment(*, registration, user, reason):
    from .models import StudentRegistration
    registration = StudentRegistration.objects.select_for_update().select_related("payment__invoice").get(pk=registration.pk)
    if not registration.payment_id:
        raise ValidationError("لا توجد دفعة مرتبطة بهذا التسجيل.")
    if registration.payment.invoice.academic_year_id:
        from accounting.models import FinancialYearClosure
        if FinancialYearClosure.objects.filter(source_year_id=registration.payment.invoice.academic_year_id).exists():
            raise ValidationError("لا يمكن حذف إيصال داخل عام مغلق ماليًا.")
    return registration.payment.safe_delete(user, reason)
