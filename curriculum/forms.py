from django import forms
from .models import Curriculum


class CurriculumForm(forms.ModelForm):
    class Meta:
        model = Curriculum
        fields = ["academic_year", "grade", "subject", "weekly_periods", "is_required", "is_active"]
