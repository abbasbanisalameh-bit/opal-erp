from django.contrib import admin
from .models import (
    Grade,
    Section,
    Subject,
    StudentRecord,
    Enrollment,
    Guardian,
    StudentGuardian,
    StudentDocument,
)


class StudentGuardianInline(admin.TabularInline):
    model = StudentGuardian
    extra = 1


class StudentDocumentInline(admin.TabularInline):
    model = StudentDocument
    extra = 1


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("name", "school", "order", "is_active")
    search_fields = ("name", "school__name")
    list_filter = ("school", "is_active")


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("name", "grade", "branch", "capacity", "is_active")
    search_fields = ("name", "grade__name", "branch__name")
    list_filter = ("branch", "grade", "is_active")


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "school", "is_active")
    search_fields = ("name", "code")
    list_filter = ("school", "is_active")


@admin.register(StudentRecord)
class StudentRecordAdmin(admin.ModelAdmin):
    list_display = ("student_number", "full_name", "father_name", "gender", "phone", "school", "branch", "is_active")
    search_fields = ("student_number", "full_name", "father_name", "phone")
    list_filter = ("school", "branch", "gender", "is_active")
    inlines = [StudentGuardianInline, StudentDocumentInline]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "academic_year", "grade", "section", "status", "joined_at")
    search_fields = ("student__full_name", "student__student_number")
    list_filter = ("academic_year", "grade", "section", "status")


@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ("full_name", "relation", "phone", "secondary_phone", "email", "school", "is_active")
    search_fields = ("full_name", "phone", "secondary_phone", "email", "national_id")
    list_filter = ("school", "relation", "is_active")


@admin.register(StudentGuardian)
class StudentGuardianAdmin(admin.ModelAdmin):
    list_display = ("student", "guardian", "is_primary", "can_receive_notifications", "can_pickup_student")
    search_fields = ("student__full_name", "guardian__full_name", "guardian__phone")
    list_filter = ("is_primary", "can_receive_notifications", "can_pickup_student")


@admin.register(StudentDocument)
class StudentDocumentAdmin(admin.ModelAdmin):
    list_display = ("student", "document_type", "title", "uploaded_at")
    search_fields = ("student__full_name", "title")
    list_filter = ("document_type", "uploaded_at")


from .models import AcademicYear, Subject

@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "grade", "is_active")
    list_filter = ("grade", "is_active")
    search_fields = ("name", "code")
