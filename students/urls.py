from django.urls import path
from . import views

app_name = "students"

urlpatterns = [
    path("", views.student_list, name="student_list"),
    path("create/", views.student_create, name="student_create"),
    path("<int:pk>/", views.student_detail, name="student_detail"),
    path("<int:pk>/update/", views.student_update, name="student_update"),
    path("<int:pk>/archive/", views.student_archive, name="student_archive"),
]
