from django.contrib import admin
from .models import (
    Grade,
    Section,
    Subject,
    Enrollment,
    StudentDocument,
)


class StudentDocumentInline(admin.TabularInline):
    model = StudentDocument
    extra = 1


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "is_kindergarten", "is_active")
    search_fields = ("name",)
    list_filter = ("is_kindergarten", "is_active")


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("name", "academic_year", "grade", "branch", "homeroom_teacher", "capacity", "is_active")
    search_fields = ("name", "grade__name", "branch__name")
    list_filter = ("academic_year", "branch", "grade", "is_active")



@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "academic_year", "grade", "section", "status", "joined_at")
    search_fields = ("student__full_name", "student__student_number")
    list_filter = ("academic_year", "grade", "section", "status")


@admin.register(StudentDocument)
class StudentDocumentAdmin(admin.ModelAdmin):
    list_display = ("student", "document_type", "title", "uploaded_at")
    search_fields = ("student__full_name", "title")
    list_filter = ("document_type", "uploaded_at")
