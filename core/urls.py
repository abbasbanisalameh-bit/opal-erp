from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("system/", views.system_settings, name="system_settings"),
    path("integrity/", views.integrity_center, name="integrity_center"),
    path("branches/", views.branch_list, name="branch_list"),
    path("branches/<int:pk>/edit/", views.branch_update, name="branch_update"),
]
