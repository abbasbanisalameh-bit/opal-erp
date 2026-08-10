from django.urls import path

from . import mobile_api


app_name = "system_mobile_api"

urlpatterns = [
    path("auth/login/", mobile_api.api_login, name="login"),
    path("auth/logout/", mobile_api.api_logout, name="logout"),
    path("me/", mobile_api.api_me, name="me"),
    path("dashboard/", mobile_api.api_dashboard, name="dashboard"),
    path("students/", mobile_api.api_students, name="students"),
    path("guardians/", mobile_api.api_guardians, name="guardians"),
    path("teachers/", mobile_api.api_teachers, name="teachers"),
    path("timetable/", mobile_api.api_timetable, name="timetable"),
    path("attendance/", mobile_api.api_attendance, name="attendance"),
    path("finance/", mobile_api.api_finance, name="finance"),
    path("exams/", mobile_api.api_exams, name="exams"),
    path("documents/", mobile_api.api_documents, name="documents"),
    path("announcements/", mobile_api.api_announcements, name="announcements"),
]
