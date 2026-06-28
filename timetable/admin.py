from django.contrib import admin
from .models import TimeSlot, TimetableEntry


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ("name", "start_time", "end_time", "order", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ("academic_year", "section", "day", "time_slot", "subject", "teacher", "room", "is_active")
    search_fields = ("section__name", "subject__name", "teacher__full_name", "room")
    list_filter = ("academic_year", "section", "day", "teacher", "is_active")
