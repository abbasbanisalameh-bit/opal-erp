from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("teachers", "0006_unified_teacher_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="Homework",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200, verbose_name="عنوان الواجب")),
                ("description", models.TextField(verbose_name="تفاصيل الواجب")),
                ("assigned_date", models.DateField(default=django.utils.timezone.localdate, verbose_name="تاريخ التكليف")),
                ("due_date", models.DateField(verbose_name="تاريخ التسليم")),
                ("attachment", models.FileField(blank=True, upload_to="homework/", verbose_name="مرفق")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assignment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="homework_items", to="teachers.teacherassignment", verbose_name="التكليف التدريسي")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_homework_items", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "واجب صفي",
                "verbose_name_plural": "الواجبات الصفية",
                "ordering": ["-assigned_date", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="homework",
            index=models.Index(fields=["assignment", "due_date", "is_active"], name="teachers_ho_assignm_f407b9_idx"),
        ),
    ]
