from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction, models
from django.utils import timezone
from core.models import Sequence
from students.models import Student
from accounting.models import FeeCategory, StudentInvoice, StudentPayment
from .models import FeePayment, FeePaymentAllocation, StudentRegistration
from .services import active_school

TWOPLACES = Decimal("0.01")


def money(value):
    return Decimal(value or 0).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def next_finance_sequence(key, prefix, padding=6):
    seq, _ = Sequence.objects.get_or_create(
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


def student_total_fees(student):
    invoices_total = sum((money(i.amount) for i in student.invoices.all()), Decimal("0.00"))
    return money(invoices_total or student.fees_total or 0)


def student_total_paid(student):
    payments_total = StudentPayment.objects.filter(invoice__student=student).aggregate(total=models.Sum("amount"))["total"] or Decimal("0.00")
    return money(payments_total or student.fees_paid or 0)


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
    q = models.Q()
    if student.phone:
        q |= models.Q(phone__iexact=student.phone.strip())
    if student.guardian_name:
        q |= models.Q(guardian_name__icontains=student.guardian_name.strip())
    if student.father_name and student.full_name:
        family_part = student.full_name.split()[-1]
        q |= models.Q(father_name__icontains=student.father_name.strip(), full_name__icontains=family_part)
    if student.mother_name:
        q |= models.Q(mother_name__icontains=student.mother_name.strip())
    if not q:
        return Student.objects.filter(pk=student.pk)
    qs = Student.objects.filter(is_active=True).filter(q).distinct().order_by("full_name")
    if not qs.filter(pk=student.pk).exists():
        qs = Student.objects.filter(pk=student.pk) | qs
    return qs.distinct().order_by("full_name")


def search_students(query):
    query = (query or "").strip()
    qs = Student.objects.filter(is_active=True).order_by("full_name")
    if not query:
        return qs.none()
    return qs.filter(
        models.Q(full_name__icontains=query) |
        models.Q(student_number__icontains=query) |
        models.Q(national_id__icontains=query) |
        models.Q(phone__icontains=query) |
        models.Q(guardian_name__icontains=query) |
        models.Q(father_name__icontains=query)
    ).distinct()[:20]


def ensure_invoice_for_student(student):
    invoice = student.invoices.filter(paid=False).order_by("due_date", "id").first()
    if invoice:
        return invoice
    remaining = student_remaining(student)
    if remaining <= 0:
        return None
    category, _ = FeeCategory.objects.get_or_create(
        name="رصيد رسوم مدرسية",
        defaults={"description": "رصيد رسوم مسجل للطالب", "amount": remaining, "active": True},
    )
    return StudentInvoice.objects.create(
        student=student,
        fee_category=category,
        amount=remaining,
        due_date=timezone.localdate(),
        paid=False,
    )


def allocate_equally_to_unpaid_siblings(students, amount):
    amount = money(amount)
    data = []
    for student in students:
        total = student_total_fees(student)
        paid = student_total_paid(student)
        remaining = money(max(total - paid, Decimal("0.00")))
        data.append({
            "student": student,
            "total": total,
            "paid": paid,
            "remaining": remaining,
            "allocated": Decimal("0.00"),
        })

    left = amount
    while left > 0:
        eligible = [x for x in data if x["remaining"] - x["allocated"] > 0]
        if not eligible:
            break
        share = money(left / Decimal(len(eligible)))
        if share <= 0:
            share = left
        progressed = False
        for item in eligible:
            capacity = money(item["remaining"] - item["allocated"])
            give = min(share, capacity, left)
            give = money(give)
            if give > 0:
                item["allocated"] = money(item["allocated"] + give)
                left = money(left - give)
                progressed = True
            if left <= 0:
                break
        if not progressed:
            break
    return data, money(left)


@transaction.atomic
def create_siblings_fee_payment(*, main_student, amount, user, notes=""):
    school = active_school()
    siblings = list(find_sibling_students(main_student))
    allocations_data, unused_amount = allocate_equally_to_unpaid_siblings(siblings, amount)
    due_before = money(sum((x["remaining"] for x in allocations_data), Decimal("0.00")))
    total_allocated = money(sum((x["allocated"] for x in allocations_data), Decimal("0.00")))
    due_after = money(max(due_before - total_allocated, Decimal("0.00")))

    fee_payment = FeePayment.objects.create(
        school=school,
        receipt_number=generate_fee_payment_receipt_number(),
        scope="all_siblings" if len(siblings) > 1 else "single",
        main_student=main_student,
        guardian_name=main_student.guardian_name,
        phone=main_student.phone,
        total_amount=total_allocated,
        total_due_before=due_before,
        total_due_after=due_after,
        created_by=user if getattr(user, "is_authenticated", False) else None,
        notes=notes or (f"مبلغ غير موزع بسبب عدم وجود رصيد مستحق: {unused_amount}" if unused_amount > 0 else ""),
    )

    for item in allocations_data:
        student = item["student"]
        allocated = money(item["allocated"])
        invoice = ensure_invoice_for_student(student) if allocated > 0 else None
        payment = None
        if invoice and allocated > 0:
            payment = StudentPayment.objects.create(
                invoice=invoice,
                amount=allocated,
                notes=f"{fee_payment.get_scope_display()} - إيصال {fee_payment.receipt_number}",
            )
            # Sync the legacy balance fields on Student for existing screens.
            student.fees_paid = money((student.fees_paid or 0) + allocated)
            student.save(update_fields=["fees_paid"])

        FeePaymentAllocation.objects.create(
            fee_payment=fee_payment,
            student=student,
            invoice=invoice,
            accounting_payment=payment,
            amount=allocated,
            total_fees=item["total"],
            paid_before=item["paid"],
            remaining_before=item["remaining"],
            remaining_after=money(max(item["remaining"] - allocated, Decimal("0.00"))),
        )

    return fee_payment
