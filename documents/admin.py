from django.contrib import admin

from .models import DocumentTemplate, IssuedDocument, StudentIssuedDocument


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "document_type", "is_active", "created_at")
    list_filter = ("document_type", "is_active")
    search_fields = ("name", "title")


@admin.register(IssuedDocument)
class IssuedDocumentAdmin(admin.ModelAdmin):
    list_display = ("document_number", "title", "student", "status", "issued_by", "issued_at")
    list_filter = ("status", "template__document_type")
    search_fields = ("document_number", "title", "student__full_name", "applicant_name")
    readonly_fields = ("verification_code", "issued_at", "cancelled_at")


@admin.register(StudentIssuedDocument)
class StudentIssuedDocumentAdmin(admin.ModelAdmin):
    list_display = ("student", "issued_document", "created_at")
    search_fields = ("student__full_name", "issued_document__document_number")
