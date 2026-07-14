# Generated for OPAL ERP parent family foundation

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("students", "0004_student_national_id"),
        ("parent_portal", "0004_alter_notification_student_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Family",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("guardian_name", models.CharField(blank=True, max_length=200, verbose_name="اسم ولي الأمر")),
                ("phone", models.CharField(blank=True, max_length=50, verbose_name="الهاتف")),
                ("national_id", models.CharField(blank=True, max_length=50, verbose_name="الرقم الوطني لولي الأمر")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="families", to="core.school")),
                ("user", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="family_account", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "أسرة", "verbose_name_plural": "الأسر"},
        ),
        migrations.CreateModel(
            name="FamilyStudent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("relation", models.CharField(default="ولي أمر", max_length=50, verbose_name="صلة القرابة")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("family", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="children", to="parent_portal.family")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="family_links", to="students.student")),
            ],
            options={"verbose_name": "طالب ضمن أسرة", "verbose_name_plural": "طلاب الأسر", "unique_together": {("family", "student")}},
        ),
    ]
