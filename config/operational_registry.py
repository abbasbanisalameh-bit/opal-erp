"""Operational settings that are driven by environment variables.

This module keeps feature flags and host/origin allow-lists centralized while
preserving the exact defaults previously declared in ``config.settings``.
"""

from .environment import env_bool, env_list


def build_feature_flags():
    """Return optional-module flags using the existing defaults."""
    return {
        "openemis": env_bool("OPAL_ENABLE_OPENEMIS", True),
        "development_center": env_bool("OPAL_ENABLE_DEVELOPMENT_CENTER", True),
    }


def build_allowed_hosts():
    """Return the existing allowed-host list."""
    return env_list(
        "OPAL_ALLOWED_HOSTS",
        [
            "Opalschool2016.pythonanywhere.com",
            "opalschool2016.pythonanywhere.com",
            "localhost",
            "127.0.0.1",
        ],
    )


def build_csrf_trusted_origins():
    """Return the existing trusted CSRF origins."""
    return env_list(
        "OPAL_CSRF_TRUSTED_ORIGINS",
        ["https://opalschool2016.pythonanywhere.com"],
    )


def get_default_auto_field():
    """Return the project's unchanged default primary-key field."""
    return "django.db.models.BigAutoField"
