from django import forms

from .models import DocumentSettings, DocumentTemplate


class DocumentTemplateForm(forms.ModelForm):
    class Meta:
        model = DocumentTemplate
        fields = ["name", "audience", "document_type", "title", "body", "is_active"]
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
        self.fields["audience"].widget.attrs["class"] = "form-select"


class DocumentSettingsForm(forms.ModelForm):
    class Meta:
        model = DocumentSettings
        fields = ["manager_name", "manager_title", "stamp_label", "footer_text"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class IssueDocumentForm(forms.Form):
    template = forms.ModelChoiceField(label="نوع الوثيقة", queryset=DocumentTemplate.objects.none())
    title = forms.CharField(label="عنوان الوثيقة", max_length=250)
    content = forms.CharField(label="نص الوثيقة", widget=forms.Textarea(attrs={"rows": 12}))
    target_school = forms.CharField(label="المدرسة المنقول إليها", required=False)
    target_grade = forms.CharField(label="الصف المنقول إليه", required=False)

    def __init__(self, *args, audience=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["template"].queryset = DocumentTemplate.objects.filter(audience=audience, is_active=True)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select" if isinstance(field.widget, forms.Select) else "form-control")
