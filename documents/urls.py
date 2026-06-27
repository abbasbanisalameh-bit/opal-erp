from django.urls import path
from . import views

app_name = "documents"

urlpatterns = [
    path("", views.document_list, name="document_list"),
    path("student/<int:student_id>/certificate/", views.issue_student_certificate, name="issue_student_certificate"),
]
