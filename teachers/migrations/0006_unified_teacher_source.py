from django.db import migrations, models
from django.db.models import Q


def normalize(value):
    table = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
    return "".join(ch for ch in str(value or "").translate(table).upper() if ch.isalnum())


def normalize_teachers(apps, schema_editor):
    Teacher = apps.get_model("teachers", "Teacher")
    seen_national = set()
    seen_ministry = set()
    for teacher in Teacher.objects.all().order_by("id"):
        national = normalize(teacher.national_id)
        ministry = normalize(teacher.ministry_teacher_id)
        extras = dict(teacher.openemis_data or {})
        if national in seen_national:
            extras.setdefault("legacy_duplicate_identifiers", []).append({"national_id": national})
            national = ""
        if ministry in seen_ministry:
            extras.setdefault("legacy_duplicate_identifiers", []).append({"ministry_teacher_id": ministry})
            ministry = ""
        if national:
            seen_national.add(national)
        if ministry:
            seen_ministry.add(ministry)
        teacher.national_id = national
        teacher.ministry_teacher_id = ministry
        teacher.openemis_data = extras
        teacher.save(update_fields=["national_id", "ministry_teacher_id", "openemis_data"])


class Migration(migrations.Migration):
    dependencies = [("teachers", "0005_teacher_is_demo_teacher_monthly_salary_and_more")]
    operations = [
        migrations.AddField(model_name="teacher", name="source", field=models.CharField(choices=[("manual", "إدخال OPAL"), ("openemis", "OpenEMIS")], default="manual", max_length=20)),
        migrations.AddField(model_name="teacher", name="ministry_teacher_id", field=models.CharField(blank=True, db_index=True, max_length=100)),
        migrations.AddField(model_name="teacher", name="openemis_data", field=models.JSONField(blank=True, default=dict)),
        migrations.AlterField(model_name="teacher", name="national_id", field=models.CharField(blank=True, db_index=True, max_length=50)),
        migrations.RunPython(normalize_teachers, migrations.RunPython.noop),
        migrations.AddConstraint(model_name="teacher", constraint=models.UniqueConstraint(condition=~Q(national_id=""), fields=("national_id",), name="uniq_teacher_national_id")),
        migrations.AddConstraint(model_name="teacher", constraint=models.UniqueConstraint(condition=~Q(ministry_teacher_id=""), fields=("ministry_teacher_id",), name="uniq_teacher_ministry_id")),
    ]
