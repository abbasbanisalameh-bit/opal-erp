from django import forms

from .models import Exam, StudentMark


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = [
            "name", "exam_type", "academic_year", "semester", "grade", "subject",
            "pass_percentage", "exam_date", "is_active",
        ]
        widgets = {"exam_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "form-check-input" if getattr(field.widget, "input_type", "") == "checkbox" else "form-control"
            field.widget.attrs.setdefault("class", css)


class StudentMarkForm(forms.ModelForm):
    class Meta:
        model = StudentMark
        fields = ["exam", "student", "mark", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["exam"].queryset = Exam.objects.filter(is_locked=False, status__in=["draft", "open"])
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
