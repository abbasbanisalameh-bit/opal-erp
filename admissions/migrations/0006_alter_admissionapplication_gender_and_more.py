# Generated for OPAL ERP canonical manual registration rules.

from django.db import migrations, models


def normalize_gender(value):
    raw = str(value or "").strip().lower()
    mapping = {
        "male": "male", "m": "male", "1": "male", "ذكر": "male", "boy": "male",
        "female": "female", "f": "female", "2": "female", "أنثى": "female", "انثى": "female", "girl": "female",
    }
    return mapping.get(raw, "")


def normalize_admission_gender(apps, schema_editor):
    for model_name in ("AdmissionApplication", "StudentRegistration"):
        Model = apps.get_model("admissions", model_name)
        for row in Model.objects.all().only("id", "gender"):
            normalized = normalize_gender(row.gender)
            if row.gender != normalized:
                Model.objects.filter(pk=row.pk).update(gender=normalized)


class Migration(migrations.Migration):
    dependencies = [
        ("admissions", "0005_unified_guardian_identity"),
    ]

    operations = [
        migrations.RunPython(normalize_admission_gender, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="admissionapplication",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[("male", "ذكر"), ("female", "أنثى")],
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="studentregistration",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[("male", "ذكر"), ("female", "أنثى")],
                max_length=20,
                verbose_name="الجنس",
            ),
        ),
        migrations.AlterField(
            model_name="studentregistration",
            name="national_id",
            field=models.CharField(
                blank=True,
                max_length=50,
                verbose_name="الرقم الوطني للطالب (OpenEMIS)",
            ),
        ),
    ]
