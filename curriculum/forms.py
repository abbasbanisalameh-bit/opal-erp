from django import forms
from .models import Curriculum


class CurriculumForm(forms.ModelForm):
    class Meta:
        model = Curriculum
        fields = ["academic_year", "grade", "subject", "weekly_periods", "is_required", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["academic_year"].queryset = self.fields["academic_year"].queryset.filter(is_closed=False)
        self.fields["grade"].queryset = self.fields["grade"].queryset.filter(is_active=True)
        self.fields["subject"].queryset = self.fields["subject"].queryset.filter(is_active=True)
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control",
            )
