from django.db import migrations, models


def remove_candidate_templates(apps, schema_editor):
    DocumentTemplate = apps.get_model("documents", "DocumentTemplate")
    IssuedDocument = apps.get_model("documents", "IssuedDocument")
    IssuedDocument.objects.filter(candidate_id__isnull=False).delete()
    DocumentTemplate.objects.filter(audience="candidate").delete()


class Migration(migrations.Migration):
    dependencies = [("documents", "0006_documenttemplate_audience_documenttemplate_code_and_more"), ("admissions", "0012_remove_candidate_admissions")]
    operations = [
        migrations.RunPython(remove_candidate_templates, migrations.RunPython.noop),
        migrations.RemoveField(model_name="issueddocument", name="candidate"),
        migrations.AlterField(
            model_name="documenttemplate",
            name="audience",
            field=models.CharField(choices=[("student", "الطالب"), ("teacher", "المعلم"), ("guardian", "ولي الأمر")], db_index=True, default="student", max_length=20),
        ),
    ]
