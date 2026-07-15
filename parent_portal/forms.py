from django import forms

from .models import Family
from .services import normalize_phone


class FamilyIdentityForm(forms.ModelForm):
    """The only website form that edits authoritative guardian identity data."""

    class Meta:
        model = Family
        fields = ["guardian_name", "relation", "identity_type", "identity_number", "phone", "secondary_phone", "email", "job_title", "address", "medical_notes"]
        labels = {
            "guardian_name": "اسم ولي الأمر",
            "phone": "رقم الهاتف",
            "relation": "صلة القرابة",
            "identity_type": "نوع الهوية",
            "identity_number": "رقم الهوية الوطنية أو الشخصية",
            "secondary_phone": "رقم هاتف إضافي",
            "email": "البريد الإلكتروني",
            "job_title": "المهنة",
            "address": "العنوان",
            "medical_notes": "ملاحظات",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
        self.fields["guardian_name"].required = True
        self.fields["phone"].required = True

    def clean_phone(self):
        return normalize_phone(self.cleaned_data.get("phone"))
