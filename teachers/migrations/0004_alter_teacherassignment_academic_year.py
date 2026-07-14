import django.db.models.deletion
from django.db import migrations, models


def copy_years(apps, schema_editor):
    Assignment = apps.get_model("teachers", "TeacherAssignment")
    LegacyYear = apps.get_model("academics", "AcademicYear")
    CoreYear = apps.get_model("core", "AcademicYear")
    School = apps.get_model("core", "School")
    default_school = School.objects.order_by("pk").first()
    for item in Assignment.objects.select_related("teacher").all():
        legacy = LegacyYear.objects.filter(pk=item.academic_year_id).first()
        school = getattr(item.teacher, "school", None) or default_school
        if not legacy or not school:
            continue
        canonical, _ = CoreYear.objects.get_or_create(
            school=school,
            name=legacy.name,
            defaults={
                "start_date": legacy.start_date,
                "end_date": legacy.end_date,
                "is_current": legacy.is_active,
            },
        )
        item.canonical_academic_year_id = canonical.pk
        item.save(update_fields=["canonical_academic_year"])


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0006_section_academic_year"),
        ("core", "0002_sequence"),
        ("teachers", "0003_teacher_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="teacherassignment",
            name="canonical_academic_year",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="core.academicyear",
            ),
        ),
        migrations.RunPython(copy_years, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="teacherassignment",
            unique_together=set(),
        ),
        migrations.RemoveField(model_name="teacherassignment", name="academic_year"),
        migrations.RenameField(
            model_name="teacherassignment",
            old_name="canonical_academic_year",
            new_name="academic_year",
        ),
        migrations.AlterField(
            model_name="teacherassignment",
            name="academic_year",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="core.academicyear",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="teacherassignment",
            unique_together={('teacher', 'academic_year', 'section', 'subject')},
        ),
    ]
