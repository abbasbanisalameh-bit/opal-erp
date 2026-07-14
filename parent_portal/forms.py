from django import forms

from .models import Family
from .services import normalize_phone


class FamilyIdentityForm(forms.ModelForm):
    """The only website form that edits authoritative guardian identity data."""

    class Meta:
        model = Family
        fields = ["guardian_name", "phone", "guardian_national_id"]
        labels = {
            "guardian_name": "اسم ولي الأمر",
            "phone": "رقم الهاتف",
            "guardian_national_id": "الرقم الوطني لولي الأمر",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.fields["guardian_name"].required = True
        self.fields["phone"].required = True

    def clean_phone(self):
        return normalize_phone(self.cleaned_data.get("phone"))
