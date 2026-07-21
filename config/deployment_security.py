"""Deployment security settings for OPAL.

This module centralizes existing security values without changing their defaults.
"""

import os

from .environment import env_bool


def get_secret_key() -> str:
    return os.environ.get(
        "OPAL_SECRET_KEY",
        "django-insecure-change-this-key-before-production",
    )


def build_proxy_ssl_header() -> tuple[str, str]:
    return ("HTTP_X_FORWARDED_PROTO", "https")


def build_production_security(*, debug: bool) -> dict[str, object]:
    if debug:
        return {}

    hsts_seconds = int(os.environ.get("OPAL_HSTS_SECONDS", "0"))
    return {
        "SECURE_CONTENT_TYPE_NOSNIFF": True,
        "SESSION_COOKIE_SECURE": True,
        "CSRF_COOKIE_SECURE": True,
        "X_FRAME_OPTIONS": "DENY",
        "SECURE_REFERRER_POLICY": "same-origin",
        "SECURE_SSL_REDIRECT": env_bool("OPAL_SECURE_SSL_REDIRECT", False),
        "SECURE_HSTS_SECONDS": hsts_seconds,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": hsts_seconds > 0,
        "SECURE_HSTS_PRELOAD": hsts_seconds > 0,
    }
