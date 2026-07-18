from django.urls import path
from . import views

app_name = "curriculum"

urlpatterns = [
    path("", views.curriculum_retired, name="curriculum_list"),
    path("add/", views.curriculum_retired, name="curriculum_create"),
    path("<int:pk>/edit/", views.curriculum_retired, name="curriculum_update"),
    path("<int:pk>/delete/", views.curriculum_retired, name="curriculum_delete"),
]
