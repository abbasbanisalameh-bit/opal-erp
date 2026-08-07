from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0013_r24_migration_identity_ordering_fix"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductionDataResetRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("previewed", "تمت المعاينة"), ("running", "قيد التنفيذ"), ("succeeded", "مكتمل"), ("failed", "فشل")], db_index=True, default="previewed", max_length=20)),
                ("preview_counts", models.JSONField(blank=True, default=dict)),
                ("deleted_counts", models.JSONField(blank=True, default=dict)),
                ("remaining_counts", models.JSONField(blank=True, default=dict)),
                ("preserved_summary", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="production_data_reset_runs", to=settings.AUTH_USER_MODEL, verbose_name="المدير المنفذ")),
            ],
            options={
                "verbose_name": "سجل تهيئة التشغيل الفعلي",
                "verbose_name_plural": "سجلات تهيئة التشغيل الفعلي",
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
