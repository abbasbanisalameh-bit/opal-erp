from django.contrib import admin
from .models import School, Branch, AcademicYear, Semester, AuditLog, Sequence, ProductionDataResetRun


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "official_name", "phone", "email", "is_active", "created_at")
    search_fields = ("name", "official_name", "phone", "email")
    list_filter = ("is_active",)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "school", "phone", "is_main", "is_active")
    search_fields = ("name", "school__name", "phone")
    list_filter = ("is_main", "is_active")


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ("name", "school", "start_date", "end_date", "is_current", "is_closed", "closed_at")
    list_filter = ("is_current", "is_closed", "school")
    search_fields = ("name", "school__name")


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ("name", "academic_year", "start_date", "end_date", "is_current")
    list_filter = ("is_current", "academic_year")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "model_name", "object_id", "user", "ip_address", "created_at")
    search_fields = ("action", "model_name", "object_id", "description", "user__username")
    list_filter = ("action", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Sequence)
class SequenceAdmin(admin.ModelAdmin):
    list_display = ("key", "prefix", "current_number", "padding", "yearly_reset")
    search_fields = ("key", "prefix")


@admin.register(ProductionDataResetRun)
class ProductionDataResetRunAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "requested_by", "started_at", "finished_at", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("requested_by__username", "error_message")
    readonly_fields = (
        "requested_by", "status", "preview_counts", "deleted_counts",
        "remaining_counts", "preserved_summary", "error_message",
        "started_at", "finished_at", "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
