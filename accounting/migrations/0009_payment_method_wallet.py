from django.db import migrations, models


PAYMENT_CHOICES = [
    ("cash", "نقدي"), ("card", "بطاقة بنكية"), ("bank_transfer", "تحويل بنكي"),
    ("online", "دفع إلكتروني"), ("wallet", "محفظة إلكترونية"), ("cheque", "شيك"),
    ("unspecified", "غير محدد (سجل سابق)"),
]


class Migration(migrations.Migration):

    dependencies = [("accounting", "0008_safe_financial_carry_forward")]

    operations = [
        migrations.AlterField(model_name="canteentransaction", name="payment_method", field=models.CharField(choices=PAYMENT_CHOICES, default="cash", max_length=30, verbose_name="طريقة الدفع")),
        migrations.AlterField(model_name="expenseentry", name="payment_method", field=models.CharField(choices=PAYMENT_CHOICES, max_length=30, verbose_name="طريقة الدفع")),
        migrations.AlterField(model_name="studentpayment", name="payment_method", field=models.CharField(choices=PAYMENT_CHOICES, db_index=True, default="unspecified", max_length=30)),
    ]
