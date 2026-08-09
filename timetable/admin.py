from django.contrib import admin
from .models import (BiometricDailySummary, BiometricDevice, ClassCoverage, SchoolDayEvent, SchoolScheduleSettings, TeacherAbsence, TeacherBiometricIdentity, TeacherBiometricPunch, TimeSlot, TimetableEntry)


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ("name", "start_time", "end_time", "order", "generated_for_smart_schedule", "is_active")
    search_fields = ("name",)
    list_filter = ("generated_for_smart_schedule", "is_active",)


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ("academic_year", "section", "day", "time_slot", "subject", "teacher", "room", "is_active")
    search_fields = ("section__name", "subject__name", "teacher__full_name", "room")
    list_filter = ("academic_year", "section", "day", "teacher", "is_active")


admin.site.register(SchoolScheduleSettings)
admin.site.register(SchoolDayEvent)
admin.site.register(TeacherAbsence)
admin.site.register(ClassCoverage)

admin.site.register(BiometricDevice)
admin.site.register(TeacherBiometricIdentity)
admin.site.register(TeacherBiometricPunch)
admin.site.register(BiometricDailySummary)
