from django.urls import path
from . import views
from . import edit_views

app_name = "attendance_v2"

urlpatterns = [
    path("", views.attendance_dashboard, name="dashboard"),
    path("take/", views.take_attendance, name="take_attendance"),
    path("edit/<int:pk>/", edit_views.attendance_edit, name="attendance_edit"),
]
