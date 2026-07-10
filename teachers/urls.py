from django.urls import path
from . import views

app_name = "teachers"
urlpatterns = [
    path("portal/", views.portal_dashboard, name="portal_dashboard"),
    path("portal/attendance/<int:assignment_pk>/", views.portal_attendance, name="portal_attendance"),
    path("portal/marks/<int:assignment_pk>/", views.portal_marks, name="portal_marks"),
    path("", views.dashboard, name="dashboard"),
    path("list/", views.teacher_list, name="teacher_list"),
    path("add/", views.teacher_create, name="teacher_create"),
    path("<int:pk>/", views.teacher_detail, name="teacher_detail"),
    path("<int:pk>/edit/", views.teacher_update, name="teacher_update"),
    path("<int:pk>/toggle/", views.teacher_toggle, name="teacher_toggle"),
    path("<int:teacher_pk>/assignments/add/", views.assignment_create, name="assignment_create"),
    path("assignments/<int:pk>/edit/", views.assignment_update, name="assignment_update"),
    path("assignments/<int:pk>/delete/", views.assignment_delete, name="assignment_delete"),
]
