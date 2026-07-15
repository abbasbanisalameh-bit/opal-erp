from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("openemis_integration", "0001_initial")]
    operations = [
        migrations.AlterField(
            model_name="openemissynclog",
            name="operation",
            field=models.CharField(
                choices=[
                    ("push_student", "إرسال طالب"),
                    ("pull_student", "سحب طالب"),
                    ("update_student", "تحديث طالب"),
                    ("sync_guardian", "مزامنة ولي الأمر"),
                    ("sync_attendance", "مزامنة الحضور"),
                    ("sync_marks", "مزامنة العلامات"),
                    ("sync_teacher", "مزامنة معلم"),
                    ("full_import", "استيراد شامل"),
                    ("test_connection", "اختبار اتصال"),
                ],
                max_length=50,
                verbose_name="العملية",
            ),
        )
    ]
