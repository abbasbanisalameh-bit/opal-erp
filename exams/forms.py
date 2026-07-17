from django import forms

from .models import Exam


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = [
            "name",
            "exam_type",
            "academic_year",
            "semester",
            "grade",
            "subject",
            "pass_percentage",
            "exam_date",
            "is_active",
        ]
        widgets = {"exam_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["academic_year"].queryset = self.fields["academic_year"].queryset.filter(is_closed=False)
        self.fields["semester"].queryset = self.fields["semester"].queryset.filter(
            academic_year__is_closed=False
        )
        self.fields["grade"].queryset = self.fields["grade"].queryset.filter(is_active=True)
        self.fields["subject"].queryset = self.fields["subject"].queryset.filter(is_active=True)
        for field in self.fields.values():
            css = "form-check-input" if getattr(field.widget, "input_type", "") == "checkbox" else "form-control"
            field.widget.attrs.setdefault("class", css)
