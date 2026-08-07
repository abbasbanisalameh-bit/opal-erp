"""Stable site-level preferences for localization, authentication, and sessions."""

import os


def build_localization():
    """Use the school authority clock; Irbid defaults to Jordan official time."""
    time_zone = os.environ.get("OPAL_TIME_ZONE", "Asia/Amman").strip() or "Asia/Amman"
    return "ar", time_zone, True, True


def build_auth_navigation():
    """Return login, post-login, and logout navigation paths."""
    return "/accounts/login/", "/", "/accounts/login/"


def build_session_preferences():
    """Return SameSite and CSRF failure preferences without changing behavior."""
    return "Lax", "Lax", "core.security.csrf_failure"
