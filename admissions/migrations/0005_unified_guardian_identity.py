from django.db import migrations, models
from django.db.models import Q


def normalize_registrations(apps, schema_editor):
    Registration = apps.get_model("admissions", "StudentRegistration")
    table = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
    seen = set()
    for row in Registration.objects.all().order_by("-created_at", "-id"):
        row.guardian_identity_number = "".join(ch for ch in str(row.guardian_identity_number or "").translate(table).upper() if ch.isalnum())
        key = (row.student_id, row.academic_year_id)
        if row.student_id and row.academic_year_id:
            if key in seen:
                row.student_id = None
            else:
                seen.add(key)
        row.save(update_fields=["guardian_identity_number", "student"])


class Migration(migrations.Migration):
    dependencies = [("admissions", "0004_studentregistration_guardian_national_id")]
    operations = [
        migrations.RenameField(model_name="studentregistration", old_name="guardian_national_id", new_name="guardian_identity_number"),
        migrations.AddField(model_name="studentregistration", name="guardian_identity_type", field=models.CharField(choices=[("national", "رقم وطني أردني"), ("personal", "رقم شخصي لغير الأردني"), ("other", "معرف آخر")], default="national", max_length=20, verbose_name="نوع هوية ولي الأمر")),
        migrations.AlterField(model_name="studentregistration", name="guardian_identity_number", field=models.CharField(blank=True, max_length=50, verbose_name="رقم هوية ولي الأمر")),
        migrations.RunPython(normalize_registrations, migrations.RunPython.noop),
        migrations.AddConstraint(model_name="studentregistration", constraint=models.UniqueConstraint(condition=Q(student__isnull=False, academic_year__isnull=False), fields=("student", "academic_year"), name="uniq_registration_per_student_year")),
    ]
