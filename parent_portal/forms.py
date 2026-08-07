from django import forms

from accounts.models import UserProfile
from students.models import Student

from .models import Family
from .services import normalize_phone


class NormalizedPhoneMixin:
    """Normalize the primary phone field consistently across family forms."""

    def clean_phone(self):
        return normalize_phone(self.cleaned_data.get("phone"))


class FamilyIdentityForm(NormalizedPhoneMixin, forms.ModelForm):
    """The only website form that edits authoritative guardian identity data."""

    class Meta:
        model = Family
        fields = ["guardian_name", "relation", "identity_type", "identity_number", "phone", "secondary_phone", "email", "job_title", "address", "medical_notes", "financial_policy"]
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
            "financial_policy": "سياسة الرسوم والدفعات",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
        self.fields["guardian_name"].required = True
        self.fields["phone"].required = True


class ParentFamilyPersonalForm(NormalizedPhoneMixin, forms.ModelForm):
    class Meta:
        model = Family
        fields = ["phone", "secondary_phone", "email", "job_title", "address", "medical_notes"]
        labels = {
            "phone": "رقم الهاتف",
            "secondary_phone": "هاتف إضافي",
            "email": "البريد الإلكتروني",
            "job_title": "المهنة",
            "address": "العنوان",
            "medical_notes": "ملاحظات شخصية",
        }
        widgets = {"address": forms.Textarea(attrs={"rows": 3}), "medical_notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class ParentPhotoForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["photo"]
        labels = {"photo": "الصورة الشخصية"}
        widgets = {"photo": forms.ClearableFileInput(attrs={"accept": "image/*", "class": "form-control"})}


class ParentStudentPersonalForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ["photo", "phone", "address", "blood_type", "medical_notes"]
        labels = {
            "photo": "صورة الطالب",
            "phone": "هاتف التواصل",
            "address": "العنوان",
            "blood_type": "فصيلة الدم",
            "medical_notes": "المعلومات الصحية",
        }
        widgets = {
            "photo": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "address": forms.Textarea(attrs={"rows": 3}),
            "medical_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
