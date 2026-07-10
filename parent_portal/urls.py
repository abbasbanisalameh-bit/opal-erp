from django.urls import path
from . import views

app_name = "parent_portal"

urlpatterns = [
    path("manage/", views.family_management, name="family_management"),
    path("", views.dashboard, name="dashboard"),
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
