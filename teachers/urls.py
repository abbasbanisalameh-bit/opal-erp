from django.urls import path
from . import views
from . import payroll_views

app_name = "teachers"
urlpatterns = [
    path("portal/", views.portal_dashboard, name="portal_dashboard"),
    path("portal/workspace/", views.portal_workspace, name="portal_workspace"),
    path("portal/timetable/", views.portal_timetable, name="portal_timetable"),
    path("portal/payroll/", payroll_views.portal_payroll, name="portal_payroll"),
    path("portal/payroll/statement/", payroll_views.portal_payroll_statement, name="portal_payroll_statement"),
    path("portal/payroll/<int:pk>/action/", payroll_views.portal_payroll_action, name="portal_payroll_action"),
    path("portal/advances/<int:pk>/acknowledge/", payroll_views.portal_advance_acknowledge, name="portal_advance_acknowledge"),
    path("portal/attendance/<int:assignment_pk>/", views.portal_attendance, name="portal_attendance"),
    path("portal/attendance/section/<int:section_pk>/", views.portal_attendance_section, name="portal_attendance_section"),
    path("portal/students/<int:assignment_pk>/", views.portal_students, name="portal_students"),
    path("portal/homework/<int:assignment_pk>/", views.portal_homework, name="portal_homework"),
    path("portal/homework/item/<int:pk>/edit/", views.portal_homework_update, name="portal_homework_update"),
    path("portal/homework/item/<int:pk>/delete/", views.portal_homework_delete, name="portal_homework_delete"),
    path("portal/marks/<int:assignment_pk>/", views.portal_marks, name="portal_marks"),
    path("", views.dashboard, name="dashboard"),
    path("list/", views.teacher_list, name="teacher_list"),
    path("add/", views.teacher_create, name="teacher_create"),
    path("<int:pk>/", views.teacher_detail, name="teacher_detail"),
    path("<int:pk>/edit/", views.teacher_update, name="teacher_update"),
    path("<int:pk>/toggle/", views.teacher_toggle, name="teacher_toggle"),
    path("<int:pk>/terminate/", payroll_views.teacher_terminate, name="teacher_terminate"),
    path("<int:pk>/account/create/", views.teacher_account_create, name="teacher_account_create"),
    path("<int:pk>/account/reset/", views.teacher_account_reset, name="teacher_account_reset"),
    path("<int:teacher_pk>/assignments/add/", views.assignment_create, name="assignment_create"),
    path("assignments/<int:pk>/edit/", views.assignment_update, name="assignment_update"),
    path("assignments/<int:pk>/delete/", views.assignment_delete, name="assignment_delete"),
    path("payroll/", payroll_views.payroll_center, name="payroll_center"),
    path("payroll/<int:pk>/edit/", payroll_views.payroll_update, name="payroll_update"),
    path("payroll/<int:pk>/send/", payroll_views.payroll_send, name="payroll_send"),
    path("advances/<int:pk>/disburse/", payroll_views.advance_disburse, name="advance_disburse"),
    path("advances/<int:pk>/reject/", payroll_views.advance_reject, name="advance_reject"),
]
