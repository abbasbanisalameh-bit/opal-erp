from django import forms
from .models import Teacher, TeacherAssignment


class DateInput(forms.DateInput):
    input_type = "date"


class TeacherForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = [
            "employee_number", "full_name", "national_id", "gender", "birth_date",
            "phone", "email", "address", "specialization", "qualification",
            "hire_date", "school", "branch", "monthly_salary", "photo", "is_active",
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

    def clean_national_id(self):
        value = (self.cleaned_data.get("national_id") or "").strip()
        if value and Teacher.objects.filter(national_id__iexact=value).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("الرقم الوطني مرتبط بمعلم آخر. افتح ملفه بدل إنشاء سجل مكرر.")
        return value


class TeacherAssignmentForm(forms.ModelForm):
    class Meta:
        model = TeacherAssignment
        fields = ["academic_year", "section", "subject", "is_primary", "is_active"]

    def __init__(self, *args, teacher=None, **kwargs):
        self.teacher = teacher or getattr(kwargs.get("instance"), "teacher", None)
        super().__init__(*args, **kwargs)
        if self.teacher:
            school = self.teacher.school
            self.fields["academic_year"].queryset = school.academic_years.all()
            self.fields["section"].queryset = self.fields["section"].queryset.filter(branch__school=school)
            self.fields["subject"].queryset = self.fields["subject"].queryset.filter(grade__school=school)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-select"

    def clean(self):
        cleaned = super().clean()
        teacher = self.teacher
        year = cleaned.get("academic_year")
        section = cleaned.get("section")
        subject = cleaned.get("subject")
        if not teacher:
            return cleaned
        if year and year.school_id != teacher.school_id:
            self.add_error("academic_year", "العام الدراسي لا يتبع مدرسة المعلم.")
        if section:
            if section.branch.school_id != teacher.school_id:
                self.add_error("section", "الشعبة لا تتبع مدرسة المعلم.")
            if year and section.academic_year_id != year.id:
                self.add_error("section", "الشعبة لا تتبع العام الدراسي المحدد.")
        if subject and section and subject.grade_id and subject.grade_id != section.grade_id:
            self.add_error("subject", "المادة لا تتبع صف الشعبة المحددة.")
        return cleaned


class TeacherAccountCreateForm(forms.Form):
    username = forms.CharField(
        required=False,
        max_length=150,
        label="اسم المستخدم",
        help_text="اتركه فارغًا ليتم توليده من الرقم الوظيفي.",
        widget=forms.TextInput(attrs={"class": "form-control", "dir": "ltr", "autocomplete": "off"}),
    )
