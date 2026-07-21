from django.apps import AppConfig


class DevelopmentCenterConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "development_center"

    def ready(self):
        from . import signals  # noqa: F401
