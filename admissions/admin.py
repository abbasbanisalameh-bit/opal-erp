from django.contrib import admin
from .models import AdmissionApplication


@admin.register(AdmissionApplication)
class AdmissionApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "application_number",
        "student_full_name",
        "guardian_name",
        "guardian_phone",
        "grade",
        "status",
        "created_at",
    )
    search_fields = (
        "application_number",
        "student_full_name",
        "guardian_name",
        "guardian_phone",
    )
    list_filter = ("status", "grade", "academic_year", "created_at")
