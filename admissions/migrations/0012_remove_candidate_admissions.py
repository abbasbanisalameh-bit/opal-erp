from django.db import migrations, models


def remove_candidate_rows(apps, schema_editor):
    AdmissionApplication = apps.get_model("admissions", "AdmissionApplication")
    AdmissionApplication.objects.filter(status="candidate").delete()


class Migration(migrations.Migration):
    dependencies = [("admissions", "0011_payment_method_wallet")]
    operations = [
        migrations.RunPython(remove_candidate_rows, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="admissionapplication",
            name="status",
            field=models.CharField(choices=[("draft", "مسودة"), ("submitted", "مقدم"), ("under_review", "قيد المراجعة"), ("approved", "مقبول"), ("rejected", "مرفوض"), ("converted", "تم تحويله لطالب")], default="draft", max_length=30),
        ),
    ]
