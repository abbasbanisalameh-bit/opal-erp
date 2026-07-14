from django.urls import path, include
from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.my_profile, name="my_profile"),
    path("roles/", views.role_list, name="role_list"),
    path("roles/<int:pk>/edit/", views.role_update, name="role_update"),
    path("", include("django.contrib.auth.urls")),
]
