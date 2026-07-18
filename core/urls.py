from django.urls import path
from . import views
from . import system_update_views
from . import webapp_reload

app_name = "core"

urlpatterns = [
    path("system/", views.system_settings, name="system_settings"),
    path("integrity/", views.integrity_center, name="integrity_center"),
    path("branches/", views.branch_list, name="branch_list"),
    path("branches/<int:pk>/edit/", views.branch_update, name="branch_update"),
    path("updates/", system_update_views.system_updates, name="system_updates"),
    path(
        "updates/reload/",
        webapp_reload.reload_webapp,
        name="updates_reload_webapp",
    ),
]

# OPAL_BACKUP_FILE_ACTIONS_V1
from . import backup_file_actions

urlpatterns += [
    path(
        "updates/files/api/",
        backup_file_actions.backup_files_api,
        name="updates_backup_files_api",
    ),
    path(
        "updates/files/download/",
        backup_file_actions.download_backup_file,
        name="updates_download_backup",
    ),
    path(
        "updates/files/delete/",
        backup_file_actions.delete_backup_file,
        name="updates_delete_backup",
    ),
]
