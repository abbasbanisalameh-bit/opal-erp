from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_academic_year_closure"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditlog",
            name="branch",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="audit_logs",
                to="core.branch",
            ),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="request_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="result",
            field=models.CharField(db_index=True, default="success", max_length=30),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="school",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="audit_logs",
                to="core.school",
            ),
        ),
    ]
