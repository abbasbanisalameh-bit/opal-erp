from django.urls import path
from . import views

app_name = "openemis"

urlpatterns = [
    path("settings/", views.settings_view, name="settings"),
    path("test/", views.test_connection_view, name="test_connection"),
    path("logs/", views.logs_view, name="logs"),
    path("student/<int:student_id>/push/", views.student_push_view, name="student_push"),
    path("student/<int:student_id>/mark-synced/", views.mark_synced_view, name="mark_synced"),
]
