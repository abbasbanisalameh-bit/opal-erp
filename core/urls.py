from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("system/", views.system_settings, name="system_settings"),
]
