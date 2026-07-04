from django import forms
from .models import Student

class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            "student_number", "national_id", "full_name",
            "guardian_name", "father_name", "mother_name",
            "gender", "blood_type", "grade", "section",
            "phone", "address", "fees_total", "fees_paid",
            "status", "enrollment_date", "photo",
            "ministry_student_id", "ministry_sync_status",
        ]
        widgets = {field: forms.TextInput(attrs={"class": "form-control"}) for field in fields}
        widgets["address"] = forms.Textarea(attrs={"class": "form-control", "rows": 3})
        widgets["status"] = forms.Select(attrs={"class": "form-control"})
        widgets["enrollment_date"] = forms.DateInput(attrs={"class": "form-control", "type": "date"})
