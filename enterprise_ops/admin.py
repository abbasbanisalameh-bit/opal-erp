from django.contrib import admin

from .models import ApprovalAction, Notification, ReportPreset, RolePermissionRule, WorkflowRequest


@admin.register(WorkflowRequest)
class WorkflowRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "request_type", "status", "priority", "requester", "assignee", "created_at")
    list_filter = ("status", "priority", "request_type")
    search_fields = ("title", "description", "requester__username", "assignee__username")


@admin.register(ApprovalAction)
class ApprovalActionAdmin(admin.ModelAdmin):
    list_display = ("workflow", "action", "actor", "created_at")
    list_filter = ("action",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "level", "is_read", "created_at")
    list_filter = ("level", "is_read")
    search_fields = ("title", "message", "recipient__username")


admin.site.register(ReportPreset)
admin.site.register(RolePermissionRule)
