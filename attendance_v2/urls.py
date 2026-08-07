from django.urls import path

from . import edit_views, views

app_name = "attendance_v2"

urlpatterns = [
    path("", views.attendance_dashboard, name="dashboard"),
    path("take/", views.take_attendance, name="take_attendance"),
    path("report/", views.attendance_report, name="report"),
    path("lock/", views.attendance_lock, name="attendance_lock"),
    path("register/<int:pk>/action/", views.attendance_register_action, name="register_action"),
    path("edit/<int:pk>/", edit_views.attendance_edit, name="attendance_edit"),
]
