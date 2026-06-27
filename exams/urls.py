from django.urls import path
from . import views

app_name = "exams"

urlpatterns = [
    path("", views.exam_list, name="exam_list"),
    path("add/", views.exam_create, name="exam_create"),
    path("marks/", views.mark_list, name="mark_list"),
    path("marks/add/", views.mark_create, name="mark_create"),
    path("<int:exam_id>/marks/bulk/", views.exam_marks_bulk, name="exam_marks_bulk"),
    path("<int:exam_id>/", views.exam_detail, name="exam_detail"),
    path("<int:exam_id>/edit/", views.exam_update, name="exam_update"),
    path("<int:exam_id>/delete/", views.exam_delete, name="exam_delete"),
]
