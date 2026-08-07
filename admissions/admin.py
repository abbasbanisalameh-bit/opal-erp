
from django.contrib import admin
from .models import RegistrationSettings, GradeFee, TransportRoute, StudentRegistration, FeePayment, FeePaymentAllocation


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


class FeePaymentAllocationInline(admin.TabularInline):
    model = FeePaymentAllocation
    extra = 0
    readonly_fields = ("student", "amount", "total_fees", "paid_before", "remaining_before", "remaining_after", "accounting_payment")


@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "scope", "guardian_name", "phone", "total_amount", "total_due_after", "created_at")
    search_fields = ("receipt_number", "guardian_name", "phone", "main_student__full_name")
    list_filter = ("scope", "created_at", "school")
    inlines = [FeePaymentAllocationInline]


@admin.register(FeePaymentAllocation)
class FeePaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ("fee_payment", "student", "amount", "remaining_after", "created_at")
    search_fields = ("fee_payment__receipt_number", "student__full_name")
