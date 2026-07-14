from django.urls import path

from . import views

app_name = "enterprise_ops"

urlpatterns = [
    path("", views.enterprise_dashboard, name="dashboard"),
    path("workflow/", views.workflow_list, name="workflow_list"),
    path("workflow/<int:pk>/", views.workflow_detail, name="workflow_detail"),
    path("workflow/<int:pk>/action/", views.workflow_action, name="workflow_action"),
    path("notifications/", views.notification_list, name="notification_list"),
    path("notifications/<int:pk>/read/", views.notification_read, name="notification_read"),
    path("notifications/read-all/", views.notification_read_all, name="notification_read_all"),
    path("audit/", views.audit_log, name="audit_log"),
    path("reports/", views.report_center, name="report_center"),
    path("permissions/", views.permission_matrix, name="permission_matrix"),
    path("reports/export/<slug:code>/", views.report_export_csv, name="report_export_csv"),
]
