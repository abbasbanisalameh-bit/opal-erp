from django.urls import path
from . import views

app_name = "development_center"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("modules/", views.module_list, name="module_list"),
    path("modules/add/", views.module_create, name="module_create"),
    path("modules/<int:pk>/edit/", views.module_update, name="module_update"),
    path("modules/<int:pk>/delete/", views.module_delete, name="module_delete"),
    path("tasks/", views.tasks_board, name="tasks_board"),

    path("releases/", views.release_list, name="release_list"),
    path("milestones/", views.milestone_list, name="milestone_list"),
    path("ideas/", views.idea_list, name="idea_list"),
    path("decisions/", views.decision_list, name="decision_list"),
    path("bugs/", views.bug_list, name="bug_list"),

]
