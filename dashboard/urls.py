from django.urls import path

from .views import executive_export_csv, home

app_name = "dashboard"

urlpatterns = [
    path("", home, name="home"),
    path("executive/export.csv", executive_export_csv, name="executive_export_csv"),
]
