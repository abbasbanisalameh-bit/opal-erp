from django.db import migrations, models
from django.db.models import Q


def normalize(value):
    table = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
    return "".join(ch for ch in str(value or "").translate(table).upper() if ch.isalnum())


def normalize_students(apps, schema_editor):
    Student = apps.get_model("students", "Student")
    seen_national = set()
    seen_ministry = set()
    for student in Student.objects.all().order_by("id"):
        national = normalize(student.national_id)
        ministry = normalize(student.ministry_student_id)
        extras = dict(student.openemis_data or {})
        if national in seen_national:
            extras.setdefault("legacy_duplicate_identifiers", []).append({"national_id": national})
            national = ""
        if ministry in seen_ministry:
            extras.setdefault("legacy_duplicate_identifiers", []).append({"ministry_student_id": ministry})
            ministry = ""
        if national:
            seen_national.add(national)
        if ministry:
            seen_ministry.add(ministry)
        student.national_id = national
        student.ministry_student_id = ministry
        student.openemis_data = extras
        student.save(update_fields=["national_id", "ministry_student_id", "openemis_data"])


class Migration(migrations.Migration):
    dependencies = [("students", "0007_student_is_demo")]
    operations = [
        migrations.AlterModelOptions(name="student", options={"ordering": ["full_name"]}),
        migrations.AddField(model_name="student", name="source", field=models.CharField(choices=[("manual", "إدخال OPAL"), ("openemis", "OpenEMIS")], default="manual", max_length=20, verbose_name="مصدر السجل")),
        migrations.AddField(model_name="student", name="openemis_data", field=models.JSONField(blank=True, default=dict, verbose_name="بيانات OpenEMIS الكاملة")),
        migrations.AlterField(model_name="student", name="national_id", field=models.CharField(blank=True, db_index=True, max_length=50, verbose_name="الرقم الوطني")),
        migrations.AlterField(model_name="student", name="ministry_student_id", field=models.CharField(blank=True, db_index=True, max_length=100, verbose_name="رقم الطالب في الوزارة")),
        migrations.RunPython(normalize_students, migrations.RunPython.noop),
        migrations.AddConstraint(model_name="student", constraint=models.UniqueConstraint(condition=~Q(national_id=""), fields=("national_id",), name="uniq_student_national_id")),
        migrations.AddConstraint(model_name="student", constraint=models.UniqueConstraint(condition=~Q(ministry_student_id=""), fields=("ministry_student_id",), name="uniq_student_ministry_id")),
    ]
