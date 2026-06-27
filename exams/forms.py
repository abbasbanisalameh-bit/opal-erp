from django import forms
from .models import Exam, StudentMark


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ["name", "exam_type", "academic_year", "grade", "subject", "max_mark", "exam_date", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "exam_type": forms.Select(attrs={"class": "form-control"}),
            "academic_year": forms.Select(attrs={"class": "form-control"}),
            "grade": forms.Select(attrs={"class": "form-control"}),
            "subject": forms.Select(attrs={"class": "form-control"}),
            "max_mark": forms.NumberInput(attrs={"class": "form-control"}),
            "exam_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class StudentMarkForm(forms.ModelForm):
    class Meta:
        model = StudentMark
        fields = ["exam", "student", "mark", "notes"]
        widgets = {
            "exam": forms.Select(attrs={"class": "form-control"}),
            "student": forms.Select(attrs={"class": "form-control"}),
            "mark": forms.NumberInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
