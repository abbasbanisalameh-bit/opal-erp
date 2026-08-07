"""Environment settings for the provider-neutral learning assistant."""

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


def build_learning_ai_settings():
    return {
        "OPAL_LEARNING_AI_PROVIDER_ENABLED": env_bool(
            "OPAL_LEARNING_AI_PROVIDER_ENABLED", False
        ),
        "OPAL_LEARNING_AI_PROVIDER_NAME": os.environ.get(
            "OPAL_LEARNING_AI_PROVIDER_NAME", "openai-compatible"
        ).strip()
        or "openai-compatible",
        "OPAL_LEARNING_AI_BASE_URL": os.environ.get(
            "OPAL_LEARNING_AI_BASE_URL", ""
        ).strip(),
        "OPAL_LEARNING_AI_API_KEY": os.environ.get(
            "OPAL_LEARNING_AI_API_KEY", ""
        ),
        "OPAL_LEARNING_AI_MODEL": os.environ.get(
            "OPAL_LEARNING_AI_MODEL", ""
        ).strip(),
        "OPAL_LEARNING_AI_TIMEOUT": max(
            5, min(120, _env_int("OPAL_LEARNING_AI_TIMEOUT", 20))
        ),
    }
