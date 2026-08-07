from django.db import migrations, models


PAYMENT_CHOICES = [
    ("cash", "نقدي"), ("card", "بطاقة بنكية"), ("bank_transfer", "تحويل بنكي"),
    ("online", "دفع إلكتروني"), ("wallet", "محفظة إلكترونية"), ("cheque", "شيك"),
    ("unspecified", "غير محدد (سجل سابق)"),
]


class Migration(migrations.Migration):

    dependencies = [("admissions", "0010_alter_admissionapplication_status")]

    operations = [
        migrations.AlterField(model_name="feepayment", name="payment_method", field=models.CharField(choices=PAYMENT_CHOICES, default="unspecified", max_length=30, verbose_name="طريقة الدفع")),
        migrations.AlterField(model_name="studentregistration", name="payment_method", field=models.CharField(choices=PAYMENT_CHOICES, default="unspecified", max_length=30, verbose_name="طريقة الدفع")),
    ]
