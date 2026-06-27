from django.contrib import admin
from .models import Exam, StudentMark


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("name", "exam_type", "academic_year", "grade", "subject", "max_mark", "exam_date", "is_active")
    list_filter = ("exam_type", "academic_year", "grade", "subject", "is_active")
    search_fields = ("name",)


@admin.register(StudentMark)
class StudentMarkAdmin(admin.ModelAdmin):
    list_display = ("student", "exam", "mark", "percentage", "created_at")
    search_fields = ("student__full_name", "exam__name")
    list_filter = ("exam",)
