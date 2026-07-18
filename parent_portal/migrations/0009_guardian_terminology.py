from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("parent_portal", "0008_unified_family_source"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="family",
            options={
                "ordering": ["guardian_name", "id"],
                "verbose_name": "ملف ولي أمر",
                "verbose_name_plural": "ملفات أولياء الأمور",
            },
        ),
        migrations.AlterModelOptions(
            name="familystudent",
            options={
                "verbose_name": "ربط طالب بولي أمر",
                "verbose_name_plural": "روابط الطلاب بأولياء الأمور",
            },
        ),
        migrations.AlterField(
            model_name="family",
            name="family_code",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=50,
                verbose_name="رقم ملف ولي الأمر",
            ),
        ),
    ]
