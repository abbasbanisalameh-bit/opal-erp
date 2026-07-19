from django.contrib import admin

from .models import (
    ApprovalAction, BroadcastMessage, FeedbackTicket, Notification,
    ReportPreset, RolePermissionRule, WorkflowRequest,
)


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
    list_display = ("title", "recipient", "level", "is_read", "sound_enabled", "created_at")
    list_filter = ("level", "is_read", "sound_enabled")
    search_fields = ("title", "message", "recipient__username")


admin.site.register(ReportPreset)
admin.site.register(RolePermissionRule)


@admin.register(FeedbackTicket)
class FeedbackTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "title", "sender", "status", "teaching_quality_rating", "electronic_services_rating", "created_at")
    list_filter = ("kind", "status", "teaching_quality_rating", "electronic_services_rating")
    search_fields = ("title", "message", "response", "sender__username")


@admin.register(BroadcastMessage)
class BroadcastMessageAdmin(admin.ModelAdmin):
    list_display = ("title", "message_type", "audience", "specific_teacher", "recipients_count", "is_active", "created_at")
    list_filter = ("message_type", "audience", "is_active")
    search_fields = ("title", "message")
