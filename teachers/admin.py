from django.contrib import admin

# Register your models here.

from .models import Homework, TeacherAssignment


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


@admin.register(Homework)
class HomeworkAdmin(admin.ModelAdmin):
    list_display = ("title", "assignment", "assigned_date", "due_date", "is_active")
    list_filter = ("is_active", "assigned_date", "due_date")
    search_fields = ("title", "description", "assignment__teacher__full_name", "assignment__section__name")
