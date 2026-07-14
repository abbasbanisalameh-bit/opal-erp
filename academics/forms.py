from django import forms
from students.models import Student
from core.models import AcademicYear, Branch
from teachers.models import Teacher

from .models import Guardian, Grade, Section


class StudentRecordForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            "full_name",
            "national_id",
            "father_name",
            "gender",
            "blood_type",
            "address",
            "medical_notes",
            "photo",
            "is_active",
        ]

        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "اسم الطالب الكامل"}),
            "national_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "الرقم الوطني"}),
            "father_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "اسم ولي الأمر / الأب"}),
            "gender": forms.Select(attrs={"class": "form-control"}),
            "blood_type": forms.TextInput(attrs={"class": "form-control", "placeholder": "فصيلة الدم"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "العنوان"}),
            "medical_notes": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "ملاحظات صحية"}),
            "photo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class StudentAdmissionForm(forms.Form):
    full_name = forms.CharField(label="اسم الطالب الكامل", widget=forms.TextInput(attrs={"class": "form-control"}))
    national_id = forms.CharField(label="الرقم الوطني", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    father_name = forms.CharField(label="اسم ولي الأمر / الأب", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    gender = forms.ChoiceField(label="الجنس", choices=[("male", "ذكر"), ("female", "أنثى")], widget=forms.Select(attrs={"class": "form-control"}))
    blood_type = forms.CharField(label="فصيلة الدم", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    address = forms.CharField(label="العنوان", required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))
    medical_notes = forms.CharField(label="ملاحظات صحية", required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))
    photo = forms.ImageField(label="صورة الطالب", required=False, widget=forms.ClearableFileInput(attrs={"class": "form-control"}))

    guardian_name = forms.CharField(label="اسم ولي الأمر", widget=forms.TextInput(attrs={"class": "form-control"}))
    guardian_relation = forms.ChoiceField(label="صلة القرابة", choices=Guardian.RELATION_CHOICES, widget=forms.Select(attrs={"class": "form-control"}))
    guardian_phone = forms.CharField(label="هاتف ولي الأمر", widget=forms.TextInput(attrs={"class": "form-control"}))
    guardian_job = forms.CharField(label="مهنة ولي الأمر", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))

    grade = forms.ModelChoiceField(label="الصف", queryset=Grade.objects.all(), widget=forms.Select(attrs={"class": "form-control"}))
    section = forms.ModelChoiceField(label="الشعبة", queryset=Section.objects.all(), required=False, widget=forms.Select(attrs={"class": "form-control"}))

from .models import Grade

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

from .models import Section

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
        fields = ["name", "start_date", "end_date", "is_current"]
        labels = {
            "name": "اسم العام الدراسي",
            "start_date": "تاريخ البداية",
            "end_date": "تاريخ النهاية",
            "is_current": "العام الحالي",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
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
