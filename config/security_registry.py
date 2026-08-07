"""Central registry for persistence and authentication security settings."""

from __future__ import annotations

import os

from .environment import env_bool


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def build_databases(base_dir):
    """Build SQLite by default or PostgreSQL when explicitly configured.

    Database credentials remain environment-only. Existing installations continue
    to use ``db.sqlite3`` until ``OPAL_DB_ENGINE=postgresql`` is set.
    """
    engine = (os.environ.get("OPAL_DB_ENGINE", "sqlite") or "sqlite").strip().lower()
    if engine in {"postgres", "postgresql", "psql"}:
        options = {}
        if env_bool("OPAL_DB_SSL_REQUIRED", True):
            options["sslmode"] = "require"
        return {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": os.environ.get("OPAL_DB_NAME", "").strip(),
                "USER": os.environ.get("OPAL_DB_USER", "").strip(),
                "PASSWORD": os.environ.get("OPAL_DB_PASSWORD", ""),
                "HOST": os.environ.get("OPAL_DB_HOST", "").strip(),
                "PORT": os.environ.get("OPAL_DB_PORT", "5432").strip(),
                "CONN_MAX_AGE": max(0, _env_int("OPAL_DB_CONN_MAX_AGE", 60)),
                "CONN_HEALTH_CHECKS": True,
                "OPTIONS": options,
            }
        }
    return {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": base_dir / "db.sqlite3",
            "OPTIONS": {"timeout": max(5, _env_int("OPAL_SQLITE_TIMEOUT", 30))},
        }
    }


def build_password_validators():
    """Return Django's password validator chain in the established order."""
    return [
        {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
        {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
        {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
        {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    ]
