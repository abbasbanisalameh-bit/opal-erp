from django.urls import path

from . import views

app_name = "enterprise_ops"

urlpatterns = [
    path("", views.enterprise_dashboard, name="dashboard"),

    # User-facing complaints and suggestions.
    path("feedback/", views.feedback_list, name="feedback_list"),
    path("feedback/new/", views.feedback_create, name="feedback_create"),
    path("feedback/<int:pk>/", views.feedback_detail, name="feedback_detail"),
    path("monthly-evaluation/submit/", views.submit_monthly_evaluations, name="submit_monthly_evaluations"),

    # Administration circulars and direct teacher alerts.
    path("broadcasts/", views.broadcast_list, name="broadcast_list"),
    path("broadcasts/new/", views.broadcast_create, name="broadcast_create"),
    path("broadcasts/<int:pk>/toggle/", views.broadcast_toggle, name="broadcast_toggle"),
    path("broadcasts/<int:pk>/delete/", views.broadcast_delete, name="broadcast_delete"),

    # Internal compatibility workflow routes.
    path("workflow/", views.workflow_list, name="workflow_list"),
    path("workflow/<int:pk>/", views.workflow_detail, name="workflow_detail"),
    path("workflow/<int:pk>/action/", views.workflow_action, name="workflow_action"),

    path("notifications/", views.notification_list, name="notification_list"),
    path("notifications/status/", views.notification_status, name="notification_status"),
    path("notifications/<int:pk>/open/", views.notification_open, name="notification_open"),
    path("notifications/<int:pk>/read/", views.notification_read, name="notification_read"),
    path("notifications/read-all/", views.notification_read_all, name="notification_read_all"),
    path("audit/", views.audit_log, name="audit_log"),
    path("reports/", views.report_center, name="report_center"),
    path("permissions/", views.permission_matrix, name="permission_matrix"),
    path("reports/export/<slug:code>/", views.report_export_csv, name="report_export_csv"),
]
