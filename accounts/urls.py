from django.urls import path, include
from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.my_profile, name="my_profile"),
    path("", include("django.contrib.auth.urls")),
]
