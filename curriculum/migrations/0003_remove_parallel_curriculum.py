from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0016_annual_subject_plan_stage"),
        ("curriculum", "0002_alter_curriculum_academic_year"),
        ("teachers", "0014_subject_plan_single_source"),
        ("timetable", "0008_subject_plan_protection"),
    ]

    operations = [
        migrations.DeleteModel(name="Curriculum"),
    ]
