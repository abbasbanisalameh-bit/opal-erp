# Generated manually for OPAL ERP fee payment and sibling payment receipts

from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("admissions", "0002_smart_registration"),
        ("accounting", "0004_alter_studentinvoice_student"),
        ("core", "0002_sequence"),
        ("students", "0005_student_is_active_student_medical_notes"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeePayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("receipt_number", models.CharField(max_length=50, unique=True, verbose_name="رقم الإيصال")),
                ("scope", models.CharField(choices=[("single", "دفعة طالب"), ("all_siblings", "دفعة عن جميع الإخوة")], default="single", max_length=30, verbose_name="نوع الدفعة")),
                ("guardian_name", models.CharField(blank=True, max_length=200, verbose_name="اسم ولي الأمر")),
                ("phone", models.CharField(blank=True, max_length=50, verbose_name="هاتف ولي الأمر")),
                ("total_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="مبلغ الدفعة")),
                ("total_due_before", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="إجمالي المتبقي قبل الدفعة")),
                ("total_due_after", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="إجمالي المتبقي بعد الدفعة")),
                ("notes", models.TextField(blank=True, verbose_name="ملاحظات")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("main_student", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="main_fee_payments", to="students.student")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fee_payments", to="core.school")),
            ],
            options={"verbose_name": "إيصال دفعة رسوم", "verbose_name_plural": "إيصالات دفعات الرسوم", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="FeePaymentAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="المدفوع في هذا الإيصال")),
                ("total_fees", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="إجمالي رسوم الطالب")),
                ("paid_before", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="المدفوع سابقًا")),
                ("remaining_before", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="المتبقي قبل الدفعة")),
                ("remaining_after", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="المتبقي بعد الدفعة")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("accounting_payment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="accounting.studentpayment")),
                ("fee_payment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="allocations", to="admissions.feepayment")),
                ("invoice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="accounting.studentinvoice")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fee_payment_allocations", to="students.student")),
            ],
            options={"verbose_name": "توزيع دفعة", "verbose_name_plural": "توزيعات الدفعات", "ordering": ["student__full_name"]},
        ),
    ]
