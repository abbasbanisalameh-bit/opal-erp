from django.urls import path
from . import views

app_name = "academics"

urlpatterns = [
    path("students/", views.student_list, name="student_list"),
    path("students/add/", views.student_create, name="student_create"),
    path("students/admission/", views.student_admission, name="student_admission"),
    path("students/<int:student_id>/", views.student_detail, name="student_detail"),
    path("students/<int:student_id>/edit/", views.student_update, name="student_update"),
]
