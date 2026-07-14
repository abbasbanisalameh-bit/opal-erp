from django.urls import path
from . import views

app_name = "parent_portal"

urlpatterns = [
    path("manage/", views.family_management, name="family_management"),
    path("manage/<int:pk>/", views.family_detail, name="family_detail"),
    path("manage/<int:pk>/edit/", views.family_update, name="family_update"),
    path("manage/<int:pk>/statement/", views.family_statement_print, name="family_statement_print"),
    path("manage/<int:pk>/statement.csv", views.family_statement_csv, name="family_statement_csv"),
    path("manage/<int:pk>/account/create/", views.family_account_create, name="family_account_create"),
    path("manage/<int:pk>/account/reset/", views.family_account_reset, name="family_account_reset"),
    path("", views.dashboard, name="dashboard"),
    path("360/", views.parent_360, name="parent_360"),
    path("children/", views.children, name="children"),
    path("fees/", views.fees, name="fees"),
    path("attendance/", views.attendance, name="attendance"),
    path("marks/", views.marks, name="marks"),
    path("timetable/", views.timetable, name="timetable"),
    path("documents/", views.documents, name="documents"),
    path("announcements/", views.announcements, name="announcements"),
    path("account/", views.account, name="account"),
    path("student/<int:student_id>/", views.student_detail, name="student_detail"),
]
