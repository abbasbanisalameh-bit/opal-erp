from django.contrib import admin

from .models import Exam, StudentMark


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("name", "exam_type", "academic_year", "semester", "grade", "subject", "max_mark", "status", "is_locked")
    list_filter = ("status", "is_locked", "exam_type", "academic_year", "grade", "subject")
    search_fields = ("name",)
    readonly_fields = ("approved_at", "published_at")


@admin.register(StudentMark)
class StudentMarkAdmin(admin.ModelAdmin):
    list_display = ("student", "exam", "mark", "percentage", "entered_by", "updated_at")
    search_fields = ("student__full_name", "student__student_number", "exam__name")
    list_filter = ("exam", "exam__status")
    readonly_fields = ("created_at", "updated_at")
