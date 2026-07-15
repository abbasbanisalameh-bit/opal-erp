import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


def normalize_identifier(value):
    table = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
    return "".join(ch for ch in str(value or "").translate(table).upper() if ch.isalnum())


def normalize_phone(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def normalize_families(apps, schema_editor):
    Family = apps.get_model("parent_portal", "Family")
    FamilyStudent = apps.get_model("parent_portal", "FamilyStudent")
    seen_identity = set()
    seen_code = set()
    for family in Family.objects.all().order_by("id"):
        identity = normalize_identifier(family.identity_number)
        phone = normalize_phone(family.phone)
        code = (family.family_code or f"FAM-{family.pk:06d}").strip()
        extras = dict(family.openemis_data or {})
        key = (family.school_id, identity)
        if identity and key in seen_identity:
            extras.setdefault("legacy_duplicate_identifiers", []).append({"identity_number": identity})
            identity = ""
        if identity:
            seen_identity.add((family.school_id, identity))
        code_key = (family.school_id, code)
        if code_key in seen_code:
            code = f"{code}-{family.pk}"
        seen_code.add((family.school_id, code))
        family.guardian_name = (family.guardian_name or family.phone or f"ولي أمر {family.pk}").strip()
        family.identity_number = identity
        family.phone = phone
        family.family_code = code
        family.openemis_data = extras
        family.save(update_fields=["guardian_name", "identity_number", "phone", "family_code", "openemis_data"])

    for student_id in FamilyStudent.objects.filter(is_active=True).values_list("student_id", flat=True).distinct():
        links = list(FamilyStudent.objects.filter(student_id=student_id, is_active=True).order_by("id"))
        for link in links[1:]:
            link.is_active = False
            link.save(update_fields=["is_active"])


def forward_guardian_identity(apps, schema_editor):
    # RenameField has already preserved guardian_national_id into identity_number.
    normalize_families(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [("parent_portal", "0007_unify_family_and_notifications")]
    operations = [
        migrations.AlterModelOptions(name="family", options={"ordering": ["guardian_name", "id"], "verbose_name": "أسرة", "verbose_name_plural": "الأسر"}),
        migrations.AlterUniqueTogether(name="familystudent", unique_together=set()),
        migrations.RenameField(model_name="family", old_name="guardian_national_id", new_name="identity_number"),
        migrations.AddField(model_name="family", name="identity_type", field=models.CharField(choices=[("national", "رقم وطني أردني"), ("personal", "رقم شخصي لغير الأردني"), ("other", "معرف آخر")], default="national", max_length=20, verbose_name="نوع الهوية")),
        migrations.AddField(model_name="family", name="source", field=models.CharField(choices=[("manual", "إدخال OPAL"), ("openemis", "OpenEMIS")], default="manual", max_length=20, verbose_name="مصدر السجل")),
        migrations.AddField(model_name="family", name="relation", field=models.CharField(default="ولي أمر", max_length=50, verbose_name="صلة القرابة")),
        migrations.AddField(model_name="family", name="secondary_phone", field=models.CharField(blank=True, max_length=50, verbose_name="هاتف إضافي")),
        migrations.AddField(model_name="family", name="email", field=models.EmailField(blank=True, max_length=254, verbose_name="البريد الإلكتروني")),
        migrations.AddField(model_name="family", name="job_title", field=models.CharField(blank=True, max_length=150, verbose_name="المهنة")),
        migrations.AddField(model_name="family", name="address", field=models.TextField(blank=True, verbose_name="العنوان")),
        migrations.AddField(model_name="family", name="medical_notes", field=models.TextField(blank=True, verbose_name="ملاحظات")),
        migrations.AddField(model_name="family", name="openemis_data", field=models.JSONField(blank=True, default=dict, verbose_name="بيانات OpenEMIS الكاملة")),
        migrations.AddField(model_name="family", name="is_active", field=models.BooleanField(default=True, verbose_name="نشطة")),
        migrations.AddField(model_name="family", name="updated_at", field=models.DateTimeField(auto_now=True)),
        migrations.AlterField(model_name="family", name="guardian_name", field=models.CharField(max_length=200, verbose_name="اسم ولي الأمر")),
        migrations.AlterField(model_name="family", name="identity_number", field=models.CharField(blank=True, db_index=True, max_length=50, verbose_name="رقم هوية ولي الأمر")),
        migrations.AlterField(model_name="family", name="phone", field=models.CharField(blank=True, db_index=True, max_length=50, verbose_name="الهاتف")),
        migrations.RunPython(forward_guardian_identity, migrations.RunPython.noop),
        migrations.AddConstraint(model_name="family", constraint=models.UniqueConstraint(condition=~Q(identity_number=""), fields=("school", "identity_number"), name="uniq_family_identity_per_school")),
        migrations.AddConstraint(model_name="family", constraint=models.UniqueConstraint(condition=~Q(family_code=""), fields=("school", "family_code"), name="uniq_family_code_per_school")),
        migrations.AddConstraint(model_name="familystudent", constraint=models.UniqueConstraint(fields=("family", "student"), name="uniq_family_student_link")),
        migrations.AddConstraint(model_name="familystudent", constraint=models.UniqueConstraint(condition=Q(is_active=True), fields=("student",), name="uniq_active_family_per_student")),
    ]
