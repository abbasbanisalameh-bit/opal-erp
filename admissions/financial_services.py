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
        .aggregate(total=models.Sum("amount"))["total"]
        or Decimal("0.00")
    )
    registration = _latest_registration(student)
    total = money(invoice_total)
    paid = money(min(accounting_paid, total)) if total > 0 else Decimal("0.00")
    remaining = money(max(total - paid, Decimal("0.00")))

    return {
        "total": total,
        "paid": paid,
        "remaining": remaining,
        "invoice_total": total,
        "accounting_paid": paid,
        "registration": registration,
    }


def student_total_fees(student):
    return student_finance_snapshot(student)["total"]


def student_total_paid(student):
    return student_finance_snapshot(student)["paid"]


def student_remaining(student):
    return money(max(student_total_fees(student) - student_total_paid(student), Decimal("0.00")))


def student_payment_status(student):
    total = student_total_fees(student)
    paid = student_total_paid(student)
    remaining = max(total - paid, Decimal("0.00"))
    if total <= 0 or remaining <= 0:
        return "paid"
    if paid <= 0:
        return "unpaid"
    return "partial"


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
        total = student_total_fees(student)
        paid = student_total_paid(student)
        rows.append({
            "student": student,
            "total": total,
            "paid": paid,
            "remaining": money(max(total - paid, Decimal("0.00"))),
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


def apply_student_payment(student, amount, receipt_number):
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
            notes=f"دفعة عن جميع الإخوة - إيصال {receipt_number}",
        )
        first_invoice = first_invoice or invoice
        first_payment = first_payment or payment
        left = Decimal("0.00")

    return first_invoice, first_payment


@transaction.atomic
def create_siblings_fee_payment(*, main_student, amount, user, notes=""):
    amount = money(amount)
    if amount <= 0:
        raise ValidationError("يجب أن يكون مبلغ الدفعة أكبر من صفر.")

    school = active_school()
    siblings = list(find_sibling_students(main_student).select_for_update())
    allocations_data, unused_amount = allocate_equally_to_unpaid_siblings(siblings, amount)
    due_before = money(sum((row["remaining"] for row in allocations_data), Decimal("0.00")))

    if due_before <= 0:
        raise ValidationError("جميع الطلاب المرتبطين بهذه الأسرة مسددون بالكامل.")
    if unused_amount > 0:
        raise ValidationError(f"المبلغ أكبر من إجمالي المتبقي للأسرة بمقدار {unused_amount} د.أ.")

    total_allocated = money(sum((row["allocated"] for row in allocations_data), Decimal("0.00")))
    due_after = money(due_before - total_allocated)
    receipt_number = generate_fee_payment_receipt_number()

    fee_payment = FeePayment.objects.create(
        school=school,
        receipt_number=receipt_number,
        scope="all_siblings" if len(siblings) > 1 else "single",
        main_student=main_student,
        guardian_name=main_student.guardian_name,
        phone=main_student.phone,
        total_amount=total_allocated,
        total_due_before=due_before,
        total_due_after=due_after,
        created_by=user if getattr(user, "is_authenticated", False) else None,
        notes=(notes or "").strip(),
    )

    for item in allocations_data:
        student = item["student"]
        allocated = money(item["allocated"])
        invoice = payment = None
        if allocated > 0:
            invoice, payment = apply_student_payment(student, allocated, receipt_number)

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

    return fee_payment
