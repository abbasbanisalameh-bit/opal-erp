from django.contrib import admin
from .models import OpenEMISSettings, OpenEMISSyncLog


@admin.register(OpenEMISSettings)
class OpenEMISSettingsAdmin(admin.ModelAdmin):
    list_display = ("school", "is_enabled", "base_url", "auto_push_registration", "auto_pull_student", "last_tested_at", "last_sync_at")
    list_filter = ("is_enabled", "auto_push_registration", "auto_pull_student")


@admin.register(OpenEMISSyncLog)
class OpenEMISSyncLogAdmin(admin.ModelAdmin):
    list_display = ("operation", "status", "student", "school", "created_by", "created_at", "completed_at")
    list_filter = ("operation", "status", "created_at")
    search_fields = ("student__full_name", "message")
    readonly_fields = ("created_at", "completed_at")
