from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_auditlog_branch_auditlog_request_id_auditlog_result_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="dataintegrityrun",
            name="school",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="integrity_runs",
                to="core.school",
            ),
        ),
    ]
