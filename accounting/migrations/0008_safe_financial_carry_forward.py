from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal


def repair_legacy_carry_forward(apps, schema_editor):
    Carry = apps.get_model("accounting", "FinancialCarryForward")
    Invoice = apps.get_model("accounting", "StudentInvoice")
    Payment = apps.get_model("accounting", "StudentPayment")
    for balance in Carry.objects.select_related("closure").all():
        sources = Invoice.objects.filter(
            academic_year_id=balance.closure.source_year_id,
            student_id=balance.student_id,
            cancellation_reason__contains="رُحّل الرصيد",
        )
        for invoice in sources:
            paid = Payment.objects.filter(invoice_id=invoice.pk, status="posted").values_list("amount", flat=True)
            paid_total = sum(paid, Decimal("0"))
            net = max((invoice.amount or Decimal("0")) - (invoice.discount_amount or Decimal("0")), Decimal("0"))
            invoice.status = "paid" if paid_total >= net else "partial" if paid_total else "open"
            invoice.paid = invoice.status == "paid"
            invoice.cancelled_by_id = None
            invoice.cancelled_at = None
            invoice.cancellation_reason = ""
            invoice.save(update_fields=["status", "paid", "cancelled_by", "cancelled_at", "cancellation_reason"])
            balance.source_invoices.add(invoice)
        if balance.target_invoice_id:
            Invoice.objects.filter(pk=balance.target_invoice_id).update(
                status="cancelled",
                paid=False,
                cancellation_reason="قيد ترحيل تركيبي سابق؛ استبدل بسجل رصيد سابق مستقل في Update 83.",
            )


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0007_expenseentry_invoice_file_expenseentry_source_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="financialcarryforward",
            name="target_invoice",
            field=models.OneToOneField(
                blank=True,
                help_text="مرجع توافق لسجلات الإصدارات السابقة فقط؛ لا تُنشأ فاتورة جديدة عند الترحيل.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="carry_forward_record",
                to="accounting.studentinvoice",
            ),
        ),
        migrations.AddField(
            model_name="financialcarryforward",
            name="source_invoices",
            field=models.ManyToManyField(blank=True, related_name="carry_forward_snapshots", to="accounting.studentinvoice"),
        ),
        migrations.AddField(
            model_name="financialcarryforward",
            name="status",
            field=models.CharField(
                choices=[("open", "رصيد سابق قائم"), ("settled", "مسدد")],
                db_index=True,
                default="open",
                max_length=20,
            ),
        ),
        migrations.RunPython(repair_legacy_carry_forward, migrations.RunPython.noop),
    ]
