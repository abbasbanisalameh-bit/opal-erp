from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        # Register lightweight, read-only runtime contracts in ``manage.py check``.
        from . import checks  # noqa: F401
