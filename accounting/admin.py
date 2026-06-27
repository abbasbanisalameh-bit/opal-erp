from django.contrib import admin
from .models import FeeCategory, StudentInvoice, StudentPayment


@admin.register(FeeCategory)
class FeeCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "amount", "active")
    search_fields = ("name",)


@admin.register(StudentInvoice)
class StudentInvoiceAdmin(admin.ModelAdmin):
    list_display = ("student", "fee_category", "amount", "due_date", "paid")
    list_filter = ("paid", "fee_category")
    search_fields = ("student__full_name",)


@admin.register(StudentPayment)
class StudentPaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "amount", "payment_date")
