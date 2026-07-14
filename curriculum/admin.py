from django.contrib import admin
from .models import Curriculum


@admin.register(Curriculum)
class CurriculumAdmin(admin.ModelAdmin):
    list_display = (
        "academic_year",
        "grade",
        "subject",
        "weekly_periods",
        "is_required",
        "is_active",
    )
    list_filter = (
        "academic_year",
        "grade",
        "is_required",
        "is_active",
    )
    search_fields = (
        "grade__name",
        "subject__name",
    )
