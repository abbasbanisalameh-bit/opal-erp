from django.urls import path
from . import views

app_name = "parent_portal"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("student/<int:student_id>/", views.student_detail, name="student_detail"),
]
