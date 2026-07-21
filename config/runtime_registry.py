"""Central runtime registry for middleware and template context processors.

The order in both registries is part of Django's runtime behavior and must remain stable.
"""


def build_middleware():
    """Return middleware in the established execution order."""
    return [
        "django.middleware.security.SecurityMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "parent_portal.middleware.ParentPortalAccessMiddleware",
        "teachers.middleware.TeacherPortalAccessMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
    ]


def build_context_processors():
    """Return global context processors in the established order."""
    return [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "announcements.context_processors.active_announcement",
        "core.context_processors.opal_identity",
        "core.context_processors.opal_operations",
        "enterprise_ops.context_processors.enterprise_notifications",
        "timetable.context_processors.live_schedule",
    ]


def ensure_development_center_middleware(middleware: list[str]) -> list[str]:
    """Return a copy with the development-center access middleware after authentication."""
    result = list(middleware)
    middleware_path = "core.middleware.DevelopmentCenterAccessMiddleware"
    if middleware_path not in result:
        auth_path = "django.contrib.auth.middleware.AuthenticationMiddleware"
        auth_index = result.index(auth_path)
        result.insert(auth_index + 1, middleware_path)
    return result
