"""Low-memory Django test settings for constrained PythonAnywhere consoles.

This module is used only when explicitly passed with
``--settings=config.settings_test_low_memory``. Production settings are not
changed.
"""

from .settings import *  # noqa: F403,F401


class DisableMigrations(dict):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

DATABASES["default"]["ENGINE"] = "django.db.backends.sqlite3"  # noqa: F405
DATABASES["default"]["NAME"] = BASE_DIR / "db.sqlite3"  # noqa: F405
DATABASES["default"]["TEST"] = {
    "NAME": "/tmp/opal_r26_low_memory_test.sqlite3",
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEBUG = False
