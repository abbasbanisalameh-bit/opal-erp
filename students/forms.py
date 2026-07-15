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
        widgets = {field: forms.TextInput(attrs={"class": "form-control"}) for field in fields}
        widgets["gender"] = forms.Select(attrs={"class": "form-select"})
        widgets["address"] = forms.Textarea(attrs={"class": "form-control", "rows": 3})
        widgets["medical_notes"] = forms.Textarea(attrs={"class": "form-control", "rows": 3})

    def clean_national_id(self):
        value = (self.cleaned_data.get("national_id") or "").strip()
        if value and Student.objects.filter(national_id__iexact=value).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("الرقم الوطني مرتبط بطالب آخر. افتح ملفه بدل إنشاء سجل مكرر.")
        return value
