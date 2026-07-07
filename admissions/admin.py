
from django.contrib import admin
from .models import AdmissionApplication, RegistrationSettings, GradeFee, TransportRoute, StudentRegistration


@admin.register(AdmissionApplication)
class AdmissionApplicationAdmin(admin.ModelAdmin):
    list_display = ("application_number", "student_full_name", "guardian_name", "guardian_phone", "grade", "status", "created_at")
    search_fields = ("application_number", "student_full_name", "guardian_name", "guardian_phone")
    list_filter = ("status", "grade", "academic_year", "created_at")


@admin.register(RegistrationSettings)
class RegistrationSettingsAdmin(admin.ModelAdmin):
    list_display = ("school", "first_payment_percent", "cash_discount_percent", "sibling_discount_percent", "updated_at")


@admin.register(GradeFee)
class GradeFeeAdmin(admin.ModelAdmin):
    list_display = ("school", "academic_year", "grade", "tuition_fee", "is_active")
    list_filter = ("school", "academic_year", "is_active")
    search_fields = ("grade__name",)


@admin.register(TransportRoute)
class TransportRouteAdmin(admin.ModelAdmin):
    list_display = ("school", "name", "full_fee", "is_active")
    list_filter = ("school", "is_active")
    search_fields = ("name",)


@admin.register(StudentRegistration)
class StudentRegistrationAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "full_name", "grade", "net_total", "first_payment", "remaining_amount", "created_at")
    list_filter = ("school", "grade", "discount_type", "transport_type", "created_at")
    search_fields = ("registration_number", "full_name", "national_id", "phone")
