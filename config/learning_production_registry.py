"""Production controls for the independent learning platform."""

from __future__ import annotations

import os

from .environment import env_bool


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def build_learning_production_settings() -> dict[str, object]:
    sales_mode = os.environ.get("OPAL_LEARNING_SUBSCRIPTION_SALES_MODE", "cards").strip().lower() or "cards"
    if sales_mode not in {"cards", "manual", "payment"}:
        sales_mode = "cards"
    return {
        "OPAL_LEARNING_PUBLIC_LAUNCH": env_bool("OPAL_LEARNING_PUBLIC_LAUNCH", False),
        "OPAL_LEARNING_SUBSCRIPTION_SALES_MODE": sales_mode,
        "OPAL_LEARNING_REQUIRE_EMAIL_VERIFICATION": env_bool(
            "OPAL_LEARNING_REQUIRE_EMAIL_VERIFICATION", True
        ),
        "OPAL_LEARNING_EMAIL_VERIFICATION_MINUTES": max(
            15, min(10080, _env_int("OPAL_LEARNING_EMAIL_VERIFICATION_MINUTES", 1440))
        ),
        "OPAL_LEARNING_API_TOKEN_DAYS": max(
            1, min(365, _env_int("OPAL_LEARNING_API_TOKEN_DAYS", 30))
        ),
        "OPAL_LEARNING_LOGIN_MAX_ATTEMPTS": max(
            3, min(20, _env_int("OPAL_LEARNING_LOGIN_MAX_ATTEMPTS", 5))
        ),
        "OPAL_LEARNING_LOGIN_LOCK_MINUTES": max(
            1, min(1440, _env_int("OPAL_LEARNING_LOGIN_LOCK_MINUTES", 15))
        ),
        "OPAL_LEARNING_API_RATE_LIMIT": max(
            10, min(10000, _env_int("OPAL_LEARNING_API_RATE_LIMIT", 120))
        ),
        "OPAL_LEARNING_LOGIN_RATE_LIMIT": max(
            3, min(100, _env_int("OPAL_LEARNING_LOGIN_RATE_LIMIT", 10))
        ),
        "OPAL_LEARNING_BACKUP_DIR": os.environ.get(
            "OPAL_LEARNING_BACKUP_DIR", ""
        ).strip(),
        "OPAL_LEARNING_BACKUP_MAX_AGE_HOURS": max(
            1, min(720, _env_int("OPAL_LEARNING_BACKUP_MAX_AGE_HOURS", 168))
        ),
    }
