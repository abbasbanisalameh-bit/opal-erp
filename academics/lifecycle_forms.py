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
        self.fields["target_year"].queryset = AcademicYear.objects.filter(is_closed=False)
        self.fields["target_section"].queryset = Section.objects.filter(
            is_active=True,
            academic_year__is_closed=False,
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("action") in {"promote", "reenroll", "section_change"}:
            if not cleaned.get("target_year") or not cleaned.get("target_grade"):
                raise forms.ValidationError("حدد العام والصف المستهدفين لهذا الإجراء.")
        return cleaned


class BulkPromotionForm(forms.Form):
    OPERATION_CHOICES = [
        ("promote", "ترفيع إلى عام وصف جديدين"),
        ("graduate", "تخريج وإنهاء القيد"),
    ]

    operation = forms.ChoiceField(label="الإجراء الجماعي", choices=OPERATION_CHOICES, initial="promote")
    source_year = forms.ModelChoiceField(label="العام الحالي", queryset=AcademicYear.objects.filter(is_closed=False))
    source_grade = forms.ModelChoiceField(label="الصف الحالي", queryset=Grade.objects.filter(is_active=True))
    target_year = forms.ModelChoiceField(
        label="العام الجديد",
        queryset=AcademicYear.objects.filter(is_closed=False),
        required=False,
    )
    target_grade = forms.ModelChoiceField(
        label="الصف الجديد",
        queryset=Grade.objects.filter(is_active=True),
        required=False,
    )
    target_section = forms.ModelChoiceField(
        label="الشعبة الجديدة",
        queryset=Section.objects.filter(is_active=True, academic_year__is_closed=False),
        required=False,
    )
    effective_date = forms.DateField(label="تاريخ الإجراء", widget=forms.DateInput(attrs={"type": "date"}))
    reason = forms.CharField(label="ملاحظات", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        operation = cleaned.get("operation")
        source_year = cleaned.get("source_year")
        source_grade = cleaned.get("source_grade")
        target_year = cleaned.get("target_year")
        target_grade = cleaned.get("target_grade")
        target_section = cleaned.get("target_section")

        if source_year and source_year.is_closed:
            self.add_error("source_year", "العام المصدر مغلق ولا يقبل حركات جديدة.")
        if source_year and source_grade and source_grade.school_id != source_year.school_id:
            self.add_error("source_grade", "الصف الحالي لا يتبع مدرسة العام المصدر.")

        if operation == "promote":
            if not target_year:
                self.add_error("target_year", "حدد العام الجديد للترفيع.")
            if not target_grade:
                self.add_error("target_grade", "حدد الصف الجديد للترفيع.")
            if source_year and target_year:
                if source_year.pk == target_year.pk:
                    self.add_error("target_year", "الترفيع يجب أن يكون إلى عام دراسي مختلف.")
                elif source_year.school_id != target_year.school_id:
                    self.add_error("target_year", "العام الجديد يجب أن يتبع المدرسة نفسها.")
            if target_year and target_grade and target_grade.school_id != target_year.school_id:
                self.add_error("target_grade", "الصف الجديد لا يتبع مدرسة العام المستهدف.")
            if target_section and target_year and target_section.academic_year_id != target_year.pk:
                self.add_error("target_section", "الشعبة الجديدة لا تتبع العام المستهدف.")
            if target_section and target_grade and target_section.grade_id != target_grade.pk:
                self.add_error("target_section", "الشعبة الجديدة لا تتبع الصف المستهدف.")
        return cleaned
