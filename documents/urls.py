from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("", views.document_list, name="document_list"),
    path("templates/", views.template_list, name="template_list"),
    path("templates/<int:pk>/edit/", views.template_update, name="template_update"),
    path("verify/<str:document_number>/<uuid:verification_code>/", views.verify_document, name="verify"),
    path("<int:document_id>/", views.document_detail, name="document_detail"),
    path("<int:document_id>/cancel/", views.document_cancel, name="document_cancel"),
    path("<int:document_id>/reissue/", views.document_reissue, name="document_reissue"),
    path("student/<int:student_id>/certificate/", views.issue_student_certificate, name="issue_student_certificate"),
]
