# Generated for OPAL ERP canonical gender choices.

from django.db import migrations, models


def normalize_gender(value):
    raw = str(value or "").strip().lower()
    mapping = {
        "male": "male", "m": "male", "1": "male", "ذكر": "male", "boy": "male",
        "female": "female", "f": "female", "2": "female", "أنثى": "female", "انثى": "female", "girl": "female",
    }
    return mapping.get(raw, "")


def normalize_students(apps, schema_editor):
    Student = apps.get_model("students", "Student")
    for student in Student.objects.all().only("id", "gender"):
        normalized = normalize_gender(student.gender)
        if student.gender != normalized:
            Student.objects.filter(pk=student.pk).update(gender=normalized)


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0008_unified_student_source"),
    ]

    operations = [
        migrations.RunPython(normalize_students, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="student",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[("male", "ذكر"), ("female", "أنثى")],
                max_length=10,
                verbose_name="الجنس",
            ),
        ),
    ]
