from django.urls import path
from . import views

app_name = "attendance_v2"

urlpatterns = [
    path("", views.attendance_dashboard, name="dashboard"),
    path("take/", views.take_attendance, name="take_attendance"),
]
