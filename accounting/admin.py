from django.contrib import admin

from .models import DiscountRequest, FeeCategory, Installment, Receipt, StudentInvoice, StudentPayment


@admin.register(FeeCategory)
class FeeCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "amount", "active")
    list_filter = ("active",)
    search_fields = ("name",)


@admin.register(StudentInvoice)
class StudentInvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "student", "fee_category", "amount", "discount_amount", "due_date", "status")
    list_filter = ("status", "fee_category", "academic_year")
    search_fields = ("invoice_number", "student__full_name", "student__student_number")
    readonly_fields = ("invoice_number", "created_at", "updated_at", "cancelled_at")


@admin.register(StudentPayment)
class StudentPaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "amount", "payment_date", "status", "created_by")
    list_filter = ("status", "payment_date")
    search_fields = ("invoice__invoice_number", "invoice__student__full_name", "reference")
    readonly_fields = ("created_at", "deleted_at")
    exclude = ("reversed_by", "reversed_at", "reversal_reason")


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "payment", "created_at", "is_void")
    search_fields = ("receipt_number", "payment__invoice__student__full_name")
    readonly_fields = ("created_at",)


@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "sequence", "title", "due_date", "amount", "status")
    list_filter = ("status", "due_date")
    search_fields = ("invoice__invoice_number", "invoice__student__full_name", "title")


@admin.register(DiscountRequest)
class DiscountRequestAdmin(admin.ModelAdmin):
    list_display = ("invoice", "requested_amount", "status", "requested_by", "created_at", "decided_by")
    list_filter = ("status",)
    search_fields = ("invoice__invoice_number", "invoice__student__full_name", "reason")
    readonly_fields = ("created_at", "decided_at")
