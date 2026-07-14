from decimal import Decimal

from django.db import migrations
from django.db.models import Sum
from django.utils import timezone


ZERO = Decimal("0.00")


def net_amount(invoice):
    return max((invoice.amount or ZERO) - (invoice.discount_amount or ZERO), ZERO)


def migrate_legacy_student_balances(apps, schema_editor):
    Student = apps.get_model("students", "Student")
    FeeCategory = apps.get_model("accounting", "FeeCategory")
    StudentInvoice = apps.get_model("accounting", "StudentInvoice")
    StudentPayment = apps.get_model("accounting", "StudentPayment")

    category, _ = FeeCategory.objects.get_or_create(
        name="رصيد مالي مرحّل",
        defaults={
            "description": "رصيد نُقل آليًا من حقول الطالب القديمة أثناء توحيد المصدر المالي",
            "amount": ZERO,
            "active": True,
        },
    )

    for student in Student.objects.all().iterator():
        invoices = list(
            StudentInvoice.objects.filter(student_id=student.pk)
            .exclude(status="cancelled")
            .order_by("due_date", "pk")
        )
        current_total = sum((net_amount(item) for item in invoices), ZERO)
        legacy_total = max(student.fees_total or ZERO, ZERO)
        target_total = max(current_total, legacy_total)

        if target_total > current_total:
            invoice = StudentInvoice.objects.create(
                student_id=student.pk,
                fee_category_id=category.pk,
                amount=target_total - current_total,
                discount_amount=ZERO,
                due_date=timezone.localdate(),
                status="open",
                paid=False,
                notes="ترحيل آلي من الرصيد المالي القديم للطالب",
            )
            invoices.append(invoice)

        current_paid = (
            StudentPayment.objects.filter(
                invoice__student_id=student.pk,
                status="posted",
            ).aggregate(total=Sum("amount"))["total"]
            or ZERO
        )
        target_paid = min(max(current_paid, student.fees_paid or ZERO), target_total)
        amount_to_migrate = target_paid - current_paid

        for invoice in invoices:
            if amount_to_migrate <= 0:
                break
            paid_on_invoice = (
                StudentPayment.objects.filter(
                    invoice_id=invoice.pk,
                    status="posted",
                ).aggregate(total=Sum("amount"))["total"]
                or ZERO
            )
            capacity = max(net_amount(invoice) - paid_on_invoice, ZERO)
            give = min(capacity, amount_to_migrate)
            if give > 0:
                StudentPayment.objects.create(
                    invoice_id=invoice.pk,
                    amount=give,
                    status="posted",
                    notes="ترحيل آلي من المدفوع القديم للطالب",
                )
                amount_to_migrate -= give

        for invoice in invoices:
            paid_on_invoice = (
                StudentPayment.objects.filter(
                    invoice_id=invoice.pk,
                    status="posted",
                ).aggregate(total=Sum("amount"))["total"]
                or ZERO
            )
            remaining = max(net_amount(invoice) - paid_on_invoice, ZERO)
            if remaining <= 0:
                status, paid = "paid", True
            elif paid_on_invoice > 0:
                status, paid = "partial", False
            else:
                status, paid = "open", False
            StudentInvoice.objects.filter(pk=invoice.pk).update(status=status, paid=paid)


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0005_student_is_active_student_medical_notes"),
        ("accounting", "0005_discountrequest_installment_and_more"),
    ]

    operations = [
        migrations.RunPython(migrate_legacy_student_balances, migrations.RunPython.noop),
        migrations.RemoveField(model_name="student", name="fees_total"),
        migrations.RemoveField(model_name="student", name="fees_paid"),
    ]
