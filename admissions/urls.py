from django.urls import path
from . import views

app_name = "admissions"

urlpatterns = [
    path("", views.admission_list, name="admission_list"),
    path("register/", views.direct_registration, name="direct_registration"),
    path("settings/", views.registration_settings, name="registration_settings"),
    path("calculate/", views.registration_calculate_api, name="registration_calculate_api"),
    path("sibling-check/", views.sibling_check_api, name="sibling_check_api"),
    path("registration/<int:pk>/receipt/", views.registration_receipt, name="registration_receipt"),
    path("payments/new/", views.fee_payment_create, name="fee_payment_create"),
    path("payments/search/", views.fee_payment_search_api, name="fee_payment_search_api"),
    path("payments/preview/", views.fee_payment_preview_api, name="fee_payment_preview_api"),
    path("payments/<int:pk>/receipt/", views.fee_payment_receipt, name="fee_payment_receipt"),
    path("payments/archive/", views.fee_payment_archive, name="fee_payment_archive"),
    path("student/<int:student_id>/financial-record/", views.student_financial_record, name="student_financial_record"),
]
