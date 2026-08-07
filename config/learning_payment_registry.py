"""Environment-only payment configuration for the independent learning platform."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from .environment import env_bool


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def build_learning_payment_settings() -> dict[str, object]:
    checkout_url = os.environ.get("OPAL_LEARNING_PAYMENT_CHECKOUT_URL", "").strip()
    parsed = urlparse(checkout_url) if checkout_url else None
    return {
        "OPAL_LEARNING_PAYMENT_ENABLED": env_bool("OPAL_LEARNING_PAYMENT_ENABLED", False),
        "OPAL_LEARNING_PAYMENT_PROVIDER": os.environ.get(
            "OPAL_LEARNING_PAYMENT_PROVIDER", "manual"
        ).strip() or "manual",
        "OPAL_LEARNING_PAYMENT_CHECKOUT_URL": checkout_url,
        "OPAL_LEARNING_PAYMENT_API_KEY": os.environ.get(
            "OPAL_LEARNING_PAYMENT_API_KEY", ""
        ),
        "OPAL_LEARNING_PAYMENT_WEBHOOK_SECRET": os.environ.get(
            "OPAL_LEARNING_PAYMENT_WEBHOOK_SECRET", ""
        ),
        "OPAL_LEARNING_PAYMENT_CURRENCY": os.environ.get(
            "OPAL_LEARNING_PAYMENT_CURRENCY", "JOD"
        ).strip().upper()[:3] or "JOD",
        "OPAL_LEARNING_PAYMENT_TIMEOUT": max(
            5, min(120, _env_int("OPAL_LEARNING_PAYMENT_TIMEOUT", 20))
        ),
        "OPAL_LEARNING_PAYMENT_CHECKOUT_HTTPS": bool(
            parsed and parsed.scheme.lower() == "https"
        ),
        "OPAL_LEARNING_MANUAL_PAYMENT_ALLOWED": env_bool(
            "OPAL_LEARNING_MANUAL_PAYMENT_ALLOWED", True
        ),
    }
