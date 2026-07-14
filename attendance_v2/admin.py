from django.contrib import admin

from .models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "status", "academic_year", "grade", "section", "is_locked")
    list_filter = ("status", "is_locked", "date", "academic_year", "grade", "section")
    search_fields = ("student__full_name", "student__student_number", "notes", "excuse_reason")
    readonly_fields = ("recorded_at", "updated_at")
