from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0014_archive_duplicate_grades"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentlifecycleevent",
            name="from_grade_snapshot",
            field=models.CharField(blank=True, max_length=100, verbose_name="الصف السابق"),
        ),
        migrations.AddField(
            model_name="studentlifecycleevent",
            name="from_section_snapshot",
            field=models.CharField(blank=True, max_length=100, verbose_name="الشعبة السابقة"),
        ),
        migrations.AddField(
            model_name="studentlifecycleevent",
            name="to_grade_snapshot",
            field=models.CharField(blank=True, max_length=100, verbose_name="الصف الجديد"),
        ),
        migrations.AddField(
            model_name="studentlifecycleevent",
            name="to_section_snapshot",
            field=models.CharField(blank=True, max_length=100, verbose_name="الشعبة الجديدة"),
        ),
    ]
