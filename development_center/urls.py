from django.urls import path
from . import views

app_name = "development_center"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("tasks/", views.task_list, name="task_list"),
    path("tasks/board/", views.tasks_board, name="tasks_board"),
    path("activity/", views.activity_list, name="activity_list"),
    path("tasks/<int:pk>/status/", views.task_update_status, name="task_update_status"),

    path("modules/", views.module_list, name="module_list"),
    path("modules/add/", views.module_create, name="module_create"),
    path("modules/<int:pk>/edit/", views.module_update, name="module_update"),
    path("modules/<int:pk>/delete/", views.module_delete, name="module_delete"),

    path("releases/", views.release_list, name="release_list"),
    path("releases/add/", views.release_create, name="release_create"),
    path("releases/<int:pk>/edit/", views.release_update, name="release_update"),
    path("releases/<int:pk>/delete/", views.release_delete, name="release_delete"),

    path("milestones/", views.milestone_list, name="milestone_list"),
    path("milestones/add/", views.milestone_create, name="milestone_create"),
    path("milestones/<int:pk>/edit/", views.milestone_update, name="milestone_update"),
    path("milestones/<int:pk>/delete/", views.milestone_delete, name="milestone_delete"),

    path("ideas/", views.idea_list, name="idea_list"),
    path("ideas/add/", views.idea_create, name="idea_create"),
    path("ideas/<int:pk>/edit/", views.idea_update, name="idea_update"),
    path("ideas/<int:pk>/delete/", views.idea_delete, name="idea_delete"),

    path("decisions/", views.decision_list, name="decision_list"),
    path("decisions/add/", views.decision_create, name="decision_create"),
    path("decisions/<int:pk>/edit/", views.decision_update, name="decision_update"),
    path("decisions/<int:pk>/delete/", views.decision_delete, name="decision_delete"),

    path("bugs/", views.bug_list, name="bug_list"),
    path("bugs/add/", views.bug_create, name="bug_create"),
    path("bugs/<int:pk>/edit/", views.bug_update, name="bug_update"),
    path("bugs/<int:pk>/delete/", views.bug_delete, name="bug_delete"),
]

urlpatterns += [
    path("tasks/add/", views.task_create, name="task_create"),
    path("tasks/<int:pk>/", views.task_detail, name="task_detail"),
    path("tasks/<int:pk>/edit/", views.task_update, name="task_update"),
    path("tasks/<int:pk>/delete/", views.task_delete, name="task_delete"),
]
