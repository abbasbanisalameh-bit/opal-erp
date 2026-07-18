from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("admissions", "0006_alter_admissionapplication_gender_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="registrationsettings",
            name="sibling_discount_once_per_family",
            field=models.BooleanField(
                default=True,
                verbose_name="خصم الإخوة مرة واحدة لكل ولي أمر",
            ),
        ),
        migrations.AlterField(
            model_name="studentregistration",
            name="family_name",
            field=models.CharField(
                blank=True,
                max_length=100,
                verbose_name="الاسم الأخير",
            ),
        ),
    ]
