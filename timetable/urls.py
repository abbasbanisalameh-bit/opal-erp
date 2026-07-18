from django.urls import path

from . import views

app_name = "timetable"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("smart-builder/", views.smart_builder, name="smart_builder"),
    path("schedule-settings/", views.schedule_settings, name="schedule_settings"),
    path("events/<int:pk>/delete/", views.event_delete, name="event_delete"),
    path("absences/", views.absence_center, name="absence_center"),
    path("coverage/<int:pk>/assign/", views.coverage_assign, name="coverage_assign"),
    path("entries/add/", views.entry_create, name="entry_create"),
    path("entries/<int:pk>/edit/", views.entry_update, name="entry_update"),
    path("entries/<int:pk>/delete/", views.entry_delete, name="entry_delete"),
    path("slots/", views.slot_list, name="slot_list"),
    path("slots/add/", views.slot_create, name="slot_create"),
    path("slots/<int:pk>/edit/", views.slot_update, name="slot_update"),
    path("slots/<int:pk>/delete/", views.slot_delete, name="slot_delete"),
    path("section/<int:section_id>/print/", views.section_print, name="section_print"),
    path("teacher/<int:teacher_id>/print/", views.teacher_print, name="teacher_print"),
]
