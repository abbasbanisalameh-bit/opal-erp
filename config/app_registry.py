"""Central registry for Django applications used by OPAL ERP.

The ordering is intentionally preserved because Django uses application order
for initialization and template/static discovery precedence.
"""

BASE_INSTALLED_APPS = (
    "learning_platform.apps.LearningPlatformConfig",
    "attendance_v2",
    "parent_portal",
    "openemis_integration",
    "accounting",
    "exams",
    "documents",
    "announcements",
    "admissions",
    "academics",
    "core",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "dashboard",
    "accounts",
    "students",
    "teachers",
    "timetable",
    "curriculum",
    "enterprise_ops.apps.EnterpriseOpsConfig",
)


def build_installed_apps(*, enable_development_center: bool) -> list[str]:
    """Return the installed-app list without changing its established order."""
    installed_apps = list(BASE_INSTALLED_APPS)
    if enable_development_center:
        installed_apps.insert(0, "development_center")
    return installed_apps


def ensure_development_center_app(installed_apps: list[str]) -> list[str]:
    """Return a copy with the development center enabled exactly once at the front."""
    result = list(installed_apps)
    if "development_center" not in result:
        result.insert(0, "development_center")
    return result
