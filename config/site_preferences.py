"""Stable site-level preferences for localization, authentication, and sessions."""


def build_localization():
    """Return localization values in the same order used by Django settings."""
    return "ar", "Asia/Amman", True, True


def build_auth_navigation():
    """Return login, post-login, and logout navigation paths."""
    return "/accounts/login/", "/", "/accounts/login/"


def build_session_preferences():
    """Return SameSite and CSRF failure preferences without changing behavior."""
    return "Lax", "Lax", "core.security.csrf_failure"
