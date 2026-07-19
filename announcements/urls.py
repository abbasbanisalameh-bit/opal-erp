from django.urls import path

from . import views

app_name = "announcements"

urlpatterns = [
    path("", views.announcement_list, name="list"),
    path("new/", views.announcement_create, name="create"),
    path("<int:pk>/edit/", views.announcement_update, name="update"),
    path("<int:pk>/toggle/", views.announcement_toggle, name="toggle"),
    path("<int:pk>/delete/", views.announcement_delete, name="delete"),
]
