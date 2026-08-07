"""One-release URL compatibility only.

LEGACY / DEPRECATED — all paths below redirect to the canonical Subject plan
screens and must be removed in OPAL Update 132.  They are intentionally absent
from navigation, workflow indexes, notifications and new code.
"""

from django.urls import path

from . import views

app_name = "curriculum"

urlpatterns = [
    path("", views.curriculum_list, name="curriculum_list"),
    path("add/", views.curriculum_create, name="curriculum_create"),
    path("<int:pk>/edit/", views.curriculum_update, name="curriculum_update"),
    path("<int:pk>/delete/", views.curriculum_delete, name="curriculum_delete"),
]
