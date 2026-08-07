from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def remove_present_records(apps, schema_editor):
    Attendance = apps.get_model("attendance_v2", "Attendance")
    Attendance.objects.filter(status="present").delete()
    Attendance.objects.filter(status="late").update(status="absent")


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("attendance_v2", "0004_simplify_attendance_statuses"),
        ("academics", "0001_initial"),
        ("core", "0001_initial"),
    ]
    operations = [
        migrations.RunPython(remove_present_records, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="attendance",
            name="status",
            field=models.CharField(choices=[("absent", "غائب"), ("departed", "مغادر")], default="absent", max_length=20),
        ),
        migrations.CreateModel(
            name="AttendanceRegister",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("is_teacher_locked", models.BooleanField(default=False)),
                ("teacher_locked_at", models.DateTimeField(blank=True, null=True)),
                ("is_admin_closed", models.BooleanField(default=False)),
                ("admin_closed_at", models.DateTimeField(blank=True, null=True)),
                ("reopen_reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("academic_year", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance_registers", to="core.academicyear")),
                ("grade", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="attendance_registers", to="academics.grade")),
                ("section", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance_registers", to="academics.section")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_attendance_registers", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_attendance_registers", to=settings.AUTH_USER_MODEL)),
                ("reopened_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reopened_attendance_registers", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-date", "section__grade__order", "section__name"]},
        ),
        migrations.AddConstraint(
            model_name="attendanceregister",
            constraint=models.UniqueConstraint(fields=("section", "date"), name="uniq_attendance_register_section_date"),
        ),
        migrations.AddIndex(
            model_name="attendanceregister",
            index=models.Index(fields=["date", "is_teacher_locked", "is_admin_closed"], name="attendance_v_date_84e196_idx"),
        ),
    ]
