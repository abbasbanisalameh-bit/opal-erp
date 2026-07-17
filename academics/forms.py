from django import forms

from core.models import AcademicYear, Branch
from teachers.models import Teacher

from .grade_names import grade_name_key, normalize_grade_display_name
from .models import Grade, Section


class AcademicStructureGradeForm(forms.Form):
    grade_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    name = forms.CharField(label="اسم الصف", max_length=100)
    order = forms.IntegerField(label="ترتيب الصف", min_value=0, initial=0)
    is_kindergarten = forms.BooleanField(label="صف روضة", required=False)
    is_active = forms.BooleanField(label="فعال", required=False, initial=True)
    tuition_fee = forms.DecimalField(label="رسوم الصف", min_value=0, max_digits=10, decimal_places=2)
    section_count = forms.IntegerField(
        label="عدد الشعب عند إنشاء الصف",
        min_value=1,
        max_value=30,
        initial=1,
        help_text="عند تعديل صف موجود لا تُحذف الشعب ولا تُنشأ بدائل تلقائيًا.",
    )
    homeroom_teacher = forms.ModelChoiceField(
        label="مربي الصف عند وجود شعبة واحدة",
        queryset=Teacher.objects.none(),
        required=False,
    )

    def __init__(self, *args, school=None, grade=None, **kwargs):
        self.school = school
        self.grade = grade
        super().__init__(*args, **kwargs)
        self.fields["homeroom_teacher"].queryset = (
            Teacher.objects.filter(school=school, is_active=True) if school else Teacher.objects.none()
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            )
        self.fields["homeroom_teacher"].widget.attrs["class"] = "form-select"

    def clean_grade_id(self):
        grade_id = self.cleaned_data.get("grade_id")
        if not grade_id:
            return None
        if not self.school or not Grade.objects.filter(pk=grade_id, school=self.school).exists():
            raise forms.ValidationError("الصف المطلوب تعديله غير موجود في المدرسة الحالية.")
        return grade_id

    def clean_name(self):
        name = normalize_grade_display_name(self.cleaned_data.get("name"))
        wanted_key = grade_name_key(name)
        if not wanted_key:
            raise forms.ValidationError("أدخل اسم صف صحيحًا.")
        if self.school:
            candidates = Grade.objects.filter(school=self.school)
            current_id = self.data.get(self.add_prefix("grade_id")) or getattr(self.grade, "pk", None)
            if current_id:
                candidates = candidates.exclude(pk=current_id)
            matching = [item for item in candidates.only("id", "name") if grade_name_key(item.name) == wanted_key]
            if matching:
                if current_id:
                    raise forms.ValidationError("هذا الصف موجود مسبقًا في الهيكل الدراسي المعتمد.")
                # Compatibility with the old add screen: entering an existing
                # canonical name updates that record instead of duplicating it.
                self.existing_grade = matching[0]
                return matching[0].name
        return name

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("grade_id") and self.add_prefix("is_active") not in self.data:
            cleaned["is_active"] = True
        return cleaned


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
            field.widget.attrs["class"] = (
                "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            )


class AcademicStructureSectionForm(forms.Form):
    section_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    grade = forms.ModelChoiceField(label="الصف", queryset=Grade.objects.none())
    name = forms.CharField(label="اسم الشعبة", max_length=50)
    capacity = forms.IntegerField(label="السعة", min_value=0, initial=0, required=False)
    homeroom_teacher = forms.ModelChoiceField(
        label="مربي الصف",
        queryset=Teacher.objects.none(),
        required=False,
    )
    is_default = forms.BooleanField(label="الشعبة الأساسية", required=False)
    is_active = forms.BooleanField(label="فعالة", required=False, initial=True)

    def __init__(self, *args, school=None, academic_year=None, section=None, **kwargs):
        self.school = school
        self.academic_year = academic_year
        self.section = section
        super().__init__(*args, **kwargs)
        if school and academic_year:
            from admissions.models import GradeFee

            grade_ids = GradeFee.objects.filter(
                school=school,
                academic_year=academic_year,
                is_active=True,
            ).values_list("grade_id", flat=True)
            self.fields["grade"].queryset = Grade.objects.filter(
                school=school,
                id__in=grade_ids,
                is_active=True,
            ).order_by("order", "name")
            self.fields["homeroom_teacher"].queryset = Teacher.objects.filter(
                school=school,
                is_active=True,
            )
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.ModelChoiceField):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean_section_id(self):
        section_id = self.cleaned_data.get("section_id")
        if not section_id:
            return None
        if not self.school or not self.academic_year:
            raise forms.ValidationError("تعذر تحديد العام الدراسي للشعبة.")
        exists = Section.objects.filter(
            pk=section_id,
            academic_year=self.academic_year,
            branch__school=self.school,
        ).exists()
        if not exists:
            raise forms.ValidationError("الشعبة المطلوب تعديلها غير موجودة في الهيكل الحالي.")
        return section_id

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError("أدخل اسم الشعبة.")
        return name

    def clean(self):
        cleaned = super().clean()
        if not self.school or not self.academic_year:
            return cleaned
        grade = cleaned.get("grade")
        name = cleaned.get("name")
        if not grade or not name:
            return cleaned
        queryset = Section.objects.filter(
            academic_year=self.academic_year,
            branch__school=self.school,
            grade=grade,
            name__iexact=name,
        )
        section_id = cleaned.get("section_id") or getattr(self.section, "pk", None)
        if section_id:
            queryset = queryset.exclude(pk=section_id)
        if queryset.exists():
            self.add_error("name", "هذه الشعبة موجودة مسبقًا لهذا الصف في العام الحالي.")
        if not cleaned.get("section_id") and self.add_prefix("is_active") not in self.data:
            cleaned["is_active"] = True
        return cleaned
