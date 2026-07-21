"""Environment value readers used by Django settings.

This module centralizes parsing only. It does not define new settings or change
any default values.
"""

import os


def env_bool(name, default=False):
    """Read a boolean environment flag using one consistent policy."""
    fallback = "True" if default else "False"
    return os.environ.get(name, fallback).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default):
    """Read a comma-separated environment variable, preserving defaults."""
    value = os.environ.get(name, "")
    if not value.strip():
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]
