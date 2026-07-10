from django import forms
from .models import Teacher, TeacherAssignment


class DateInput(forms.DateInput):
    input_type = "date"


class TeacherForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = [
            "user", "employee_number", "full_name", "national_id", "gender", "birth_date",
            "phone", "email", "address", "specialization", "qualification",
            "hire_date", "school", "branch", "photo", "is_active",
        ]
        widgets = {
            "birth_date": DateInput(), "hire_date": DateInput(),
            "address": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"


class TeacherAssignmentForm(forms.ModelForm):
    class Meta:
        model = TeacherAssignment
        fields = ["academic_year", "section", "subject", "is_primary", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-select"
