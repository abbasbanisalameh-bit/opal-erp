from django.db import migrations, models


def convert_excused_to_absent(apps, schema_editor):
    Attendance = apps.get_model("attendance_v2", "Attendance")
    Attendance.objects.filter(status="excused").update(status="absent")


class Migration(migrations.Migration):
    dependencies = [
        ("attendance_v2", "0003_alter_attendance_options_attendance_academic_year_and_more"),
    ]

    operations = [
        migrations.RunPython(convert_excused_to_absent, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="attendance",
            name="status",
            field=models.CharField(
                choices=[
                    ("present", "حاضر"),
                    ("absent", "غائب"),
                    ("late", "متأخر"),
                    ("departed", "مغادر"),
                ],
                default="present",
                max_length=20,
            ),
        ),
    ]
