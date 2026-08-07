import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0016_annual_subject_plan_stage"),
        ("timetable", "0007_smart_break_groups_and_generated_slots"),
    ]

    operations = [
        migrations.AlterField(
            model_name="timetableentry",
            name="subject",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="academics.subject"),
        ),
    ]
