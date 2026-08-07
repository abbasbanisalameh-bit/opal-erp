import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0016_annual_subject_plan_stage"),
        ("teachers", "0013_teacher_workload_and_free_period_policy"),
    ]

    operations = [
        migrations.AlterField(
            model_name="teacherassignment",
            name="subject",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="academics.subject"),
        ),
        migrations.RemoveField(
            model_name="teacherassignment",
            name="weekly_periods",
        ),
    ]
