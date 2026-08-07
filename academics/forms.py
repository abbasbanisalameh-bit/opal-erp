from datetime import timedelta

from django import forms

from core.models import AcademicYear
from teachers.models import Teacher

from .grade_names import grade_name_key, normalize_grade_display_name, normalize_section_name, section_name_key
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
    """Edit the official two-semester calendar without duplicating storage.

    The user enters the four semester boundaries directly. Internally, OPAL
    keeps using AcademicYear.midyear_break_start/end as the canonical bridge
    fields and AcademicYear.ensure_semesters() updates the existing Semester
    rows. No parallel calendar model is introduced.
    """

    first_semester_end = forms.DateField(
        label="نهاية الفصل الدراسي الأول",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    second_semester_start = forms.DateField(
        label="بداية الفصل الدراسي الثاني",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )

    class Meta:
        model = AcademicYear
        fields = ["name", "start_date", "first_semester_end", "second_semester_start", "end_date", "is_current"]
        labels = {
            "name": "اسم العام الدراسي",
            "start_date": "بداية الفصل الدراسي الأول",
            "end_date": "نهاية الفصل الدراسي الثاني",
            "is_current": "العام الحالي",
        }
        widgets = {
            "start_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "end_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }

    def __init__(self, *args, school=None, **kwargs):
        self.school = school
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            first = self.instance.semesters.filter(code="first").first()
            second = self.instance.semesters.filter(code="second").first()
            if first:
                self.fields["first_semester_end"].initial = first.end_date
            elif self.instance.midyear_break_start:
                self.fields["first_semester_end"].initial = self.instance.midyear_break_start - timedelta(days=1)
            if second:
                self.fields["second_semester_start"].initial = second.start_date
            elif self.instance.midyear_break_end:
                self.fields["second_semester_start"].initial = self.instance.midyear_break_end + timedelta(days=1)
        elif not self.is_bound and self.school:
            # Suggest the next calendar from the latest existing academic year.
            # Only the year component changes; the manager remains free to edit
            # all proposed dates before saving.
            previous_year = (
                AcademicYear.objects.filter(school=self.school)
                .order_by("-start_date", "-pk")
                .first()
            )
            if previous_year:
                previous_first = previous_year.semesters.filter(code="first").first()
                previous_second = previous_year.semesters.filter(code="second").first()
                first_end = (
                    previous_first.end_date
                    if previous_first
                    else previous_year.midyear_break_start - timedelta(days=1)
                    if previous_year.midyear_break_start
                    else None
                )
                second_start = (
                    previous_second.start_date
                    if previous_second
                    else previous_year.midyear_break_end + timedelta(days=1)
                    if previous_year.midyear_break_end
                    else None
                )

                def next_year_date(value):
                    if value is None:
                        return None
                    try:
                        return value.replace(year=value.year + 1)
                    except ValueError:
                        # 29 February becomes 28 February in a non-leap year.
                        return value.replace(year=value.year + 1, day=28)

                proposed = {
                    "start_date": next_year_date(previous_year.start_date),
                    "first_semester_end": next_year_date(first_end),
                    "second_semester_start": next_year_date(second_start),
                    "end_date": next_year_date(previous_year.end_date),
                }
                for field_name, value in proposed.items():
                    if value is not None:
                        self.fields[field_name].initial = value
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            )
            if isinstance(field.widget, forms.DateInput):
                field.widget.attrs.setdefault("inputmode", "numeric")
                field.widget.attrs.setdefault("autocomplete", "off")

    def clean(self):
        cleaned = super().clean()
        first_start = cleaned.get("start_date")
        first_end = cleaned.get("first_semester_end")
        second_start = cleaned.get("second_semester_start")
        second_end = cleaned.get("end_date")

        if first_start and first_end and first_end < first_start:
            self.add_error("first_semester_end", "نهاية الفصل الأول يجب ألا تسبق بدايته.")
        if first_end and second_start and second_start <= first_end:
            self.add_error("second_semester_start", "بداية الفصل الثاني يجب أن تكون بعد نهاية الفصل الأول.")
        if second_start and second_end and second_end < second_start:
            self.add_error("end_date", "نهاية الفصل الثاني يجب ألا تسبق بدايته.")

        # ModelForm runs model validation after clean(). Keep the canonical
        # bridge fields synchronized here so AcademicYear.clean() validates
        # the dates the user just entered, not stale hidden values.
        if first_end and second_start and second_start > first_end:
            self.instance.midyear_break_start = first_end + timedelta(days=1)
            self.instance.midyear_break_end = second_start - timedelta(days=1)
        return cleaned

    def save(self, commit=True):
        year = super().save(commit=False)
        first_end = self.cleaned_data["first_semester_end"]
        second_start = self.cleaned_data["second_semester_start"]
        # Preserve the existing canonical database contract. The dates between
        # these boundaries are the inter-semester holiday.
        year.midyear_break_start = first_end + timedelta(days=1)
        year.midyear_break_end = second_start - timedelta(days=1)
        if commit:
            year.save()
            self.save_m2m()
        return year


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
        grade = self.data.get(self.add_prefix("grade"))
        grade_obj = Grade.objects.filter(pk=grade).first() if grade else getattr(self.section, "grade", None)
        return normalize_section_name(name, getattr(grade_obj, "name", ""))

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
        )
        section_id = cleaned.get("section_id") or getattr(self.section, "pk", None)
        if section_id:
            queryset = queryset.exclude(pk=section_id)
        wanted_key = section_name_key(name, grade.name)
        if any(section_name_key(item.name, grade.name) == wanted_key for item in queryset.only("name")):
            self.add_error("name", "هذه الشعبة موجودة مسبقًا لهذا الصف في العام الحالي.")
        if not cleaned.get("section_id") and self.add_prefix("is_active") not in self.data:
            cleaned["is_active"] = True
        return cleaned


class SubjectPlanForm(forms.ModelForm):
    """The single material + annual plan form; no parallel Curriculum model."""

    class Meta:
        from .models import Subject
        model = Subject
        fields = [
            "academic_year", "grade", "name", "code", "weekly_periods",
            "is_required", "color", "is_active",
        ]
        labels = {
            "academic_year": "العام الدراسي",
            "grade": "الصف",
            "name": "اسم المادة",
            "code": "رمز المادة",
            "weekly_periods": "عدد الحصص أسبوعيًا",
            "is_required": "مادة إلزامية",
            "color": "لون المادة الموحد",
            "is_active": "فعالة",
        }
        widgets = {
            "color": forms.TextInput(attrs={"type": "color"}),
        }

    def __init__(self, *args, school=None, **kwargs):
        self.school = school
        super().__init__(*args, **kwargs)
        if school:
            self.fields["academic_year"].queryset = AcademicYear.objects.filter(
                school=school, is_closed=False
            ).order_by("-is_current", "-start_date")
            self.fields["grade"].queryset = Grade.objects.filter(
                school=school, is_active=True
            ).order_by("order", "name")
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        year = cleaned.get("academic_year")
        grade = cleaned.get("grade")
        if year and grade and year.school_id != grade.school_id:
            self.add_error("grade", "الصف يجب أن يتبع مدرسة العام الدراسي.")

        if self.instance.pk and year and grade:
            scope_changed = (
                year.pk != self.instance.academic_year_id
                or grade.pk != self.instance.grade_id
            )
            has_history = (
                self.instance.teacherassignment_set.exists()
                or self.instance.timetableentry_set.exists()
                or self.instance.exams.exists()
                or self.instance.semester_results.exists()
                or self.instance.annual_results.exists()
            )
            if scope_changed and has_history:
                self.add_error(
                    "academic_year",
                    "لا يمكن نقل مادة مرتبطة بتكليف أو جدول أو امتحان أو نتيجة إلى عام أو صف آخر. أنشئ مادة سنوية صحيحة بدلًا من كسر السجل التاريخي.",
                )
        return cleaned
