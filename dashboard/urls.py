from django.urls import path

from .views import attendance_detail, executive_export_csv, home

app_name = "dashboard"

urlpatterns = [
    path("", home, name="home"),
    path("attendance-details/", attendance_detail, name="attendance_detail"),
    path("executive/export.csv", executive_export_csv, name="executive_export_csv"),
]
