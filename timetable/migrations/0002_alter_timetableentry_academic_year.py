import django.db.models.deletion
from django.db import migrations, models


def copy_years(apps, schema_editor):
    Entry = apps.get_model("timetable", "TimetableEntry")
    LegacyYear = apps.get_model("academics", "AcademicYear")
    CoreYear = apps.get_model("core", "AcademicYear")
    School = apps.get_model("core", "School")
    default_school = School.objects.order_by("pk").first()
    for item in Entry.objects.select_related("section__branch__school").all():
        legacy = LegacyYear.objects.filter(pk=item.academic_year_id).first()
        school = None
        try:
            school = item.section.branch.school
        except Exception:
            school = default_school
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
        ("timetable", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="timetableentry",
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
            name="timetableentry",
            unique_together=set(),
        ),
        migrations.RemoveField(model_name="timetableentry", name="academic_year"),
        migrations.RenameField(
            model_name="timetableentry",
            old_name="canonical_academic_year",
            new_name="academic_year",
        ),
        migrations.AlterField(
            model_name="timetableentry",
            name="academic_year",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="core.academicyear",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="timetableentry",
            unique_together={("academic_year", "section", "day", "time_slot")},
        ),
    ]
