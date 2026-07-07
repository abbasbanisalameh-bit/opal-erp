
from django.urls import path
from . import views

app_name = "admissions"

urlpatterns = [
    path("", views.admission_list, name="admission_list"),
    path("register/", views.direct_registration, name="direct_registration"),
    path("settings/", views.registration_settings, name="registration_settings"),
    path("calculate/", views.registration_calculate_api, name="registration_calculate_api"),
    path("registration/<int:pk>/receipt/", views.registration_receipt, name="registration_receipt"),
]
