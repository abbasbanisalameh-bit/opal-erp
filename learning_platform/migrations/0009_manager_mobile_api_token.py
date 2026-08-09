from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("learning_platform", "0008_school_learning_bridge"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LearningManagerAPIToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(db_index=True, max_length=64, unique=True, verbose_name="بصمة الرمز")),
                ("token_prefix", models.CharField(db_index=True, max_length=12, verbose_name="بداية الرمز")),
                ("device_name", models.CharField(blank=True, max_length=120, verbose_name="اسم الجهاز")),
                ("expires_at", models.DateTimeField(db_index=True, verbose_name="ينتهي في")),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="learning_manager_api_tokens", to=settings.AUTH_USER_MODEL, verbose_name="مستخدم OPAL ERP")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="learningmanagerapitoken",
            index=models.Index(fields=["user", "revoked_at", "expires_at"], name="learn_mgr_api_user_idx"),
        ),
    ]
