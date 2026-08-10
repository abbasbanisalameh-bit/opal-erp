from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0014_productiondataresetrun"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SystemMobileAPIToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(db_index=True, max_length=128, unique=True)),
                ("token_prefix", models.CharField(db_index=True, max_length=16)),
                ("device_name", models.CharField(blank=True, max_length=120)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="opal_system_mobile_tokens", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "رمز تطبيق نظام أوبال",
                "verbose_name_plural": "رموز تطبيق نظام أوبال",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="systemmobileapitoken",
            index=models.Index(fields=["user", "revoked_at", "expires_at"], name="core_system_user_id_4d66b3_idx"),
        ),
    ]
