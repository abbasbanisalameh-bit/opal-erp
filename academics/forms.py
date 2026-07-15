from django import forms

from core.models import AcademicYear, Branch
from teachers.models import Teacher

from .models import Grade, Section


class GradeForm(forms.ModelForm):
    class Meta:
        model = Grade
        fields = ["name", "order", "is_kindergarten", "is_active"]
        labels = {
            "name": "اسم الصف",
            "order": "ترتيب العرض",
            "is_kindergarten": "صف روضة",
            "is_active": "فعال",
        }

    def __init__(self, *args, school=None, **kwargs):
        self.school = school
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if self.school and Grade.objects.filter(school=self.school, name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("هذا الصف موجود مسبقًا في المدرسة.")
        return name


class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = ["academic_year", "branch", "grade", "name", "capacity", "homeroom_teacher", "is_default", "is_active"]
        labels = {
            "academic_year": "العام الدراسي",
            "branch": "الفرع",
            "grade": "الصف",
            "name": "اسم الشعبة",
            "capacity": "السعة",
            "homeroom_teacher": "مربي الصف",
            "is_default": "الشعبة الأساسية",
            "is_active": "فعالة",
        }

    def __init__(self, *args, school=None, academic_year=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields["academic_year"].queryset = AcademicYear.objects.filter(school=school)
            self.fields["branch"].queryset = Branch.objects.filter(school=school, is_active=True)
            self.fields["grade"].queryset = Grade.objects.filter(school=school, is_active=True)
            self.fields["homeroom_teacher"].queryset = Teacher.objects.filter(school=school, is_active=True)
        if academic_year and not self.is_bound:
            self.fields["academic_year"].initial = academic_year
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-select"


class AcademicStructureGradeForm(forms.Form):
    name = forms.CharField(label="اسم الصف", max_length=100)
    order = forms.IntegerField(label="ترتيب الصف", min_value=0, initial=0)
    is_kindergarten = forms.BooleanField(label="صف روضة", required=False)
    tuition_fee = forms.DecimalField(label="رسوم الصف", min_value=0, max_digits=10, decimal_places=2)
    section_count = forms.IntegerField(label="عدد الشعب", min_value=1, max_value=30, initial=1)
    homeroom_teacher = forms.ModelChoiceField(label="مربي الصف عند وجود شعبة واحدة", queryset=Teacher.objects.none(), required=False)

    def __init__(self, *args, school=None, **kwargs):
        self.school = school
        super().__init__(*args, **kwargs)
        self.fields["homeroom_teacher"].queryset = Teacher.objects.filter(school=school, is_active=True) if school else Teacher.objects.none()
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
        self.fields["homeroom_teacher"].widget.attrs["class"] = "form-select"

    def clean_name(self):
        return (self.cleaned_data.get("name") or "").strip()


class AcademicStructureYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ["name", "start_date", "midyear_break_start", "midyear_break_end", "end_date", "is_current"]
        labels = {
            "name": "اسم العام الدراسي",
            "start_date": "تاريخ البداية",
            "midyear_break_start": "بداية عطلة منتصف العام",
            "midyear_break_end": "نهاية عطلة منتصف العام",
            "end_date": "تاريخ النهاية",
            "is_current": "العام الحالي",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "midyear_break_start": forms.DateInput(attrs={"type": "date"}),
            "midyear_break_end": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, school=None, **kwargs):
        self.school = school
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"


class AcademicStructureSectionForm(forms.Form):
    grade = forms.ModelChoiceField(label="الصف", queryset=Grade.objects.none())
    name = forms.CharField(label="اسم الشعبة", max_length=50)
    capacity = forms.IntegerField(label="السعة", min_value=0, initial=0, required=False)
    homeroom_teacher = forms.ModelChoiceField(label="مربي الصف", queryset=Teacher.objects.none(), required=False)

    def __init__(self, *args, school=None, academic_year=None, **kwargs):
        self.school = school
        self.academic_year = academic_year
        super().__init__(*args, **kwargs)
        if school and academic_year:
            from admissions.models import GradeFee
            grade_ids = GradeFee.objects.filter(school=school, academic_year=academic_year, is_active=True).values_list("grade_id", flat=True)
            self.fields["grade"].queryset = Grade.objects.filter(school=school, id__in=grade_ids, is_active=True).order_by("order", "name")
            self.fields["homeroom_teacher"].queryset = Teacher.objects.filter(school=school, is_active=True)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.ModelChoiceField) else "form-control"

    def clean_name(self):
        return (self.cleaned_data.get("name") or "").strip()
