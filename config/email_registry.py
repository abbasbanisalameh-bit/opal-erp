"""Environment-driven email settings for independent learning-account recovery."""

import os

from .environment import env_bool


def _env_int(name, default):
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def build_learning_email_settings():
    use_tls = env_bool("OPAL_LEARNING_EMAIL_USE_TLS", True)
    use_ssl = env_bool("OPAL_LEARNING_EMAIL_USE_SSL", False)
    if use_tls and use_ssl:
        use_ssl = False
    return {
        "OPAL_LEARNING_EMAIL_ENABLED": env_bool("OPAL_LEARNING_EMAIL_ENABLED", False),
        "OPAL_LEARNING_PASSWORD_RESET_MINUTES": _env_int(
            "OPAL_LEARNING_PASSWORD_RESET_MINUTES", 60
        ),
        "EMAIL_BACKEND": os.environ.get(
            "OPAL_LEARNING_EMAIL_BACKEND",
            "django.core.mail.backends.smtp.EmailBackend",
        ).strip()
        or "django.core.mail.backends.smtp.EmailBackend",
        "EMAIL_HOST": os.environ.get("OPAL_LEARNING_EMAIL_HOST", "").strip(),
        "EMAIL_PORT": _env_int("OPAL_LEARNING_EMAIL_PORT", 587),
        "EMAIL_HOST_USER": os.environ.get("OPAL_LEARNING_EMAIL_USER", "").strip(),
        "EMAIL_HOST_PASSWORD": os.environ.get("OPAL_LEARNING_EMAIL_PASSWORD", ""),
        "EMAIL_USE_TLS": use_tls,
        "EMAIL_USE_SSL": use_ssl,
        "EMAIL_TIMEOUT": _env_int("OPAL_LEARNING_EMAIL_TIMEOUT", 15),
        "DEFAULT_FROM_EMAIL": os.environ.get(
            "OPAL_LEARNING_DEFAULT_FROM_EMAIL",
            "no-reply@opal-learning.local",
        ).strip()
        or "no-reply@opal-learning.local",
    }
