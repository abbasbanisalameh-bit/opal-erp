from django.apps import AppConfig


class EnterpriseOpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "enterprise_ops"
    verbose_name = "الإشعارات والشكاوى والتنبيهات"

    def ready(self):
        from . import signals  # noqa: F401
