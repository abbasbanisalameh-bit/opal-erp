from django import forms

from core.models import AcademicYear
from .models import Grade, Section, StudentLifecycleEvent


class StudentLifecycleForm(forms.Form):
    action = forms.ChoiceField(label="الإجراء", choices=StudentLifecycleEvent.ACTION_CHOICES)
    effective_date = forms.DateField(label="تاريخ الإجراء", widget=forms.DateInput(attrs={"type": "date"}))
    target_year = forms.ModelChoiceField(label="العام المستهدف", queryset=AcademicYear.objects.all(), required=False)
    target_grade = forms.ModelChoiceField(label="الصف المستهدف", queryset=Grade.objects.filter(is_active=True), required=False)
    target_section = forms.ModelChoiceField(label="الشعبة المستهدفة", queryset=Section.objects.filter(is_active=True), required=False)
    reason = forms.CharField(label="السبب / الملاحظات", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("action") in {"promote", "reenroll", "section_change"}:
            if not cleaned.get("target_year") or not cleaned.get("target_grade"):
                raise forms.ValidationError("حدد العام والصف المستهدفين لهذا الإجراء.")
        return cleaned


class BulkPromotionForm(forms.Form):
    source_year = forms.ModelChoiceField(label="العام الحالي", queryset=AcademicYear.objects.all())
    source_grade = forms.ModelChoiceField(label="الصف الحالي", queryset=Grade.objects.filter(is_active=True))
    target_year = forms.ModelChoiceField(label="العام الجديد", queryset=AcademicYear.objects.all())
    target_grade = forms.ModelChoiceField(label="الصف الجديد", queryset=Grade.objects.filter(is_active=True))
    target_section = forms.ModelChoiceField(label="الشعبة الجديدة", queryset=Section.objects.filter(is_active=True), required=False)
    effective_date = forms.DateField(label="تاريخ الترفيع", widget=forms.DateInput(attrs={"type": "date"}))
    reason = forms.CharField(label="ملاحظات", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
