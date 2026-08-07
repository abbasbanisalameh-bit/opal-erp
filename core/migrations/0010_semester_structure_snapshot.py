from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_academic_lifecycle_states"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SemesterStructureSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payload", models.JSONField(default=dict, verbose_name="بيانات البنية التاريخية")),
                ("is_final", models.BooleanField(db_index=True, default=False, verbose_name="لقطة إغلاق نهائية")),
                ("captured_at", models.DateTimeField(auto_now=True, verbose_name="وقت الالتقاط")),
                ("captured_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="captured_semester_structures", to=settings.AUTH_USER_MODEL, verbose_name="التقطها")),
                ("semester", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="structure_snapshot", to="core.semester", verbose_name="الفصل الدراسي")),
                ("source_snapshot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="derived_snapshots", to="core.semesterstructuresnapshot", verbose_name="لقطة الفصل المصدر")),
            ],
            options={"ordering": ["semester__academic_year__start_date", "semester__code"]},
        ),
    ]
