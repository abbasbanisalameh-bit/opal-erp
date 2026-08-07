from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parent_portal", "0013_alter_teachermonthlyevaluation_electronic_services_rating"),
    ]

    operations = [
        migrations.AlterField(
            model_name="family",
            name="financial_policy",
            field=models.CharField(
                choices=[
                    ("alert_only", "تنبيه فقط دون حجب"),
                    ("hide_results", "حجب النتائج فقط"),
                    ("hide_certificates", "حجب الشهادات والوثائق فقط"),
                    ("restrict_noncritical", "تقييد الخدمات غير الأساسية"),
                    ("exceptional_suspension", "تعليق استثنائي بقرار الإدارة"),
                ],
                default="alert_only",
                help_text="الوضع الافتراضي تنبيه فقط؛ الحضور والتنبيهات الأساسية لا تُحجب.",
                max_length=30,
                verbose_name="سياسة الرسوم والدفعات",
            ),
        ),
    ]
