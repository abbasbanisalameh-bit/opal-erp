from django.contrib import admin
from .models import DocumentTemplate, IssuedDocument


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "document_type",
        "is_active",
        "created_at",
    )
    list_filter = (
        "document_type",
        "is_active",
    )
    search_fields = (
        "name",
        "title",
    )


@admin.register(IssuedDocument)
class IssuedDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "document_number",
        "title",
        "student",
        "issued_by",
        "issued_at",
    )
    search_fields = (
        "document_number",
        "title",
    )
