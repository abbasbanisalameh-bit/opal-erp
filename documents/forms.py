from django import forms

from .models import DocumentTemplate


class DocumentTemplateForm(forms.ModelForm):
    class Meta:
        model = DocumentTemplate
        fields = ["name", "document_type", "title", "body", "is_active"]
        labels = {
            "name": "اسم القالب",
            "document_type": "نوع الوثيقة",
            "title": "عنوان الوثيقة",
            "body": "نص الوثيقة",
            "is_active": "فعال",
        }
        widgets = {"body": forms.Textarea(attrs={"rows": 8})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
        self.fields["document_type"].widget.attrs["class"] = "form-select"
