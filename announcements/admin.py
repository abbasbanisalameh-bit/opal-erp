from django.contrib import admin
from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "announcement_type",
        "is_active",
        "speed_seconds",
        "created_at",
    )
    list_filter = (
        "announcement_type",
        "is_active",
    )
    search_fields = (
        "title",
        "message",
    )
