from django import forms
from .models import Student


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            "student_number",
            "full_name",
            "guardian_name",
            "father_name",
            "grade",
            "section",
            "phone",
            "address",
            "fees_total",
            "fees_paid",
            "status",
            "enrollment_date",
            "photo",
        ]
        widgets = {
            "enrollment_date": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 3}),
        }
