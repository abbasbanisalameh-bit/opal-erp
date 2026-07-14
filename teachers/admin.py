from django.contrib import admin

# Register your models here.

from .models import TeacherAssignment


@admin.register(TeacherAssignment)
class TeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "teacher",
        "academic_year",
        "section",
        "subject",
        "is_primary",
        "is_active",
    )
    list_filter = (
        "academic_year",
        "section",
        "subject",
        "is_active",
    )
    search_fields = (
        "teacher__full_name",
        "subject__name",
        "section__name",
    )
