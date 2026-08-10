"""Central URL groups for OPAL ERP.

This module only organizes the existing project-level includes. Route order,
prefixes, namespaces, and feature flags remain controlled by ``config.urls``.
"""
from django.urls import include, path

PRIMARY_URLPATTERNS = [
    path("mobile/api/v1/", include("core.mobile_api_urls")),
    path("learning/", include("learning_platform.urls")),
    path("students/", include("students.urls")),
    path("parent/", include("parent_portal.urls")),
]

CORE_URLPATTERNS = [
    path("accounts/", include("accounts.urls")),
    path("settings/", include("core.urls")),
    path("", include("dashboard.urls")),
]

SCHOOL_URLPATTERNS = [
    path("academics/", include("academics.urls")),
    path("curriculum/", include("curriculum.urls")),
    path("admissions/", include("admissions.urls")),
    path("documents/", include("documents.urls")),
    path("exams/", include("exams.urls")),
    path("accounting/", include("accounting.urls")),
    path("attendance/", include("attendance_v2.urls")),
    path("teachers/", include("teachers.urls")),
    path("timetable/", include("timetable.urls")),
    path("enterprise/", include("enterprise_ops.urls")),
    path("announcements/", include("announcements.urls")),
]
