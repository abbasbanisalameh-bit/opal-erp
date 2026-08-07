from django import forms
from .models import Student

class StudentForm(forms.ModelForm):
    """Edit personal data only; academic placement has its own lifecycle screen."""

    class Meta:
        model = Student
        fields = [
            "national_id", "full_name", "father_name", "mother_name",
            "gender", "blood_type", "address", "medical_notes", "photo",
        ]
        widgets = {
            "national_id": forms.TextInput(attrs={"class": "form-control"}),
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "father_name": forms.TextInput(attrs={"class": "form-control"}),
            "mother_name": forms.TextInput(attrs={"class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-select"}),
            "blood_type": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "medical_notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "photo": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["photo"].help_text = "الحد الأقصى لحجم الصورة: 1 ميجابايت."

    def clean_national_id(self):
        value = (self.cleaned_data.get("national_id") or "").strip()
        if value and Student.objects.filter(national_id__iexact=value).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("الرقم الوطني مرتبط بطالب آخر. افتح ملفه بدل إنشاء سجل مكرر.")
        return value
