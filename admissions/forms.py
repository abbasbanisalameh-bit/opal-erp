
from django import forms

from core.identifiers import normalize_identifier
from .models import AdmissionApplication, GradeFee, TransportRoute, RegistrationSettings, StudentRegistration
from academics.models import Grade, Section
from students.models import Student


class AdmissionApplicationForm(forms.ModelForm):
    class Meta:
        model = AdmissionApplication
        exclude = ("school", "branch", "academic_year", "application_number", "status", "notes", "created_at")
        widgets = {
            "student_full_name": forms.TextInput(attrs={"class": "form-control"}),
            "father_name": forms.TextInput(attrs={"class": "form-control"}),
            "mother_name": forms.TextInput(attrs={"class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-select"}),
            "birth_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "photo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "guardian_name": forms.TextInput(attrs={"class": "form-control"}),
            "guardian_phone": forms.TextInput(attrs={"class": "form-control"}),
            "guardian_email": forms.EmailInput(attrs={"class": "form-control"}),
            "guardian_job": forms.TextInput(attrs={"class": "form-control"}),
            "grade": forms.Select(attrs={"class": "form-select"}),
            "section": forms.Select(attrs={"class": "form-select"}),
        }


class GradeFeeForm(forms.ModelForm):
    class Meta:
        model = GradeFee
        fields = ["academic_year", "grade", "tuition_fee", "is_active"]
        labels = {"academic_year": "العام الدراسي", "grade": "الصف", "tuition_fee": "رسوم الصف", "is_active": "فعالة"}
        widgets = {
            "academic_year": forms.Select(attrs={"class": "form-select"}),
            "grade": forms.Select(attrs={"class": "form-select"}),
            "tuition_fee": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, school=None, academic_year=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields["academic_year"].queryset = school.academic_years.all()
            self.fields["grade"].queryset = Grade.objects.filter(school=school, is_active=True)
        if academic_year and not self.is_bound:
            self.fields["academic_year"].initial = academic_year


class TransportRouteForm(forms.ModelForm):
    class Meta:
        model = TransportRoute
        fields = ["name", "full_fee", "is_active", "notes"]
        labels = {"name": "اسم الجولة", "full_fee": "رسوم ذهاب وعودة", "is_active": "فعالة", "notes": "ملاحظات"}
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "full_fee": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class RegistrationSettingsForm(forms.ModelForm):
    class Meta:
        model = RegistrationSettings
        fields = [
            "first_payment_percent", "cash_discount_percent", "sibling_discount_percent",
            "quran_25_percent", "quran_50_percent", "quran_75_percent", "quran_100_percent",
            "enable_cash_discount", "enable_sibling_discount", "enable_quran_discount", "enable_admin_discount",
            "sibling_discount_once_per_family",
        ]
        labels = {
            "first_payment_percent": "نسبة الدفعة الأولى الافتراضية",
            "cash_discount_percent": "نسبة خصم الكاش",
            "sibling_discount_percent": "نسبة خصم الإخوة",
            "quran_25_percent": "خصم القرآن 25%",
            "quran_50_percent": "خصم القرآن 50%",
            "quran_75_percent": "خصم القرآن 75%",
            "quran_100_percent": "خصم القرآن 100%",
            "enable_cash_discount": "تفعيل خصم الكاش",
            "enable_sibling_discount": "تفعيل خصم الإخوة",
            "enable_quran_discount": "تفعيل خصم القرآن",
            "enable_admin_discount": "تفعيل خصم الإدارة",
            "sibling_discount_once_per_family": "خصم الإخوة مرة واحدة للعائلة",
        }
        widgets = {field: forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}) for field in [
            "first_payment_percent", "cash_discount_percent", "sibling_discount_percent", "quran_25_percent", "quran_50_percent", "quran_75_percent", "quran_100_percent"
        ]}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})


class DirectStudentRegistrationForm(forms.ModelForm):
    class Meta:
        model = StudentRegistration
        fields = [
            "first_name", "father_name", "grandfather_name", "family_name", "gender", "birth_date", "photo",
            "guardian_name", "guardian_identity_type", "guardian_identity_number", "mother_name", "phone", "address", "grade", "section",
            "transport_route", "transport_type", "discount_type", "admin_discount_value", "sibling_student", "first_payment", "notes",
        ]
        labels = {
            "first_name": "الاسم الأول", "father_name": "اسم الأب", "grandfather_name": "اسم الجد", "family_name": "اسم العائلة",
            "gender": "الجنس", "birth_date": "تاريخ الميلاد", "photo": "صورة الطالب",
            "guardian_name": "اسم ولي الأمر", "guardian_identity_type": "نوع هوية ولي الأمر", "guardian_identity_number": "الرقم الوطني أو الشخصي لولي الأمر", "mother_name": "اسم الأم", "phone": "هاتف ولي الأمر", "address": "العنوان",
            "grade": "الصف", "section": "الشعبة", "transport_route": "جولة المواصلات", "transport_type": "نوع المواصلات",
            "discount_type": "نوع الخصم", "admin_discount_value": "قيمة خصم الإدارة", "sibling_student": "الأخ المسجل", "first_payment": "الدفعة الأولى", "notes": "ملاحظات",
        }
        widgets = {
            "gender": forms.Select(),
            "birth_date": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "first_payment": forms.NumberInput(attrs={"step": "0.01", "readonly": "readonly", "inputmode": "decimal"}),
            "admin_discount_value": forms.NumberInput(attrs={"step": "0.01"}),
        }

    def __init__(self, *args, school=None, academic_year=None, **kwargs):
        self.school = school
        self.academic_year = academic_year
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.update({"class": "form-select"})
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                field.widget.attrs.update({"class": "form-control"})
        self.fields["sibling_student"].queryset = Student.objects.filter(is_active=True).order_by("full_name")
        self.fields["sibling_student"].required = False
        self.fields["transport_route"].required = False
        self.fields["section"].required = False
        self.fields["photo"].required = False
        self.fields["first_payment"].required = False
        self.fields["first_payment"].help_text = "تُحسب تلقائيًا من صافي الرسوم وفق النسبة المحددة في إعدادات التسجيل."
        if not self.is_bound:
            self.fields["first_payment"].initial = None
        self.fields["admin_discount_value"].initial = 0
        self.fields["guardian_name"].required = True
        self.fields["guardian_identity_type"].required = True
        self.fields["guardian_identity_number"].required = True
        self.fields["guardian_identity_number"].help_text = "المعرف العائلي الفريد الذي يربط جميع الإخوة بولي الأمر نفسه."
        self.fields["gender"].required = True
        self.fields["phone"].required = True
        if school and academic_year:
            configured_grade_ids = GradeFee.objects.filter(
                school=school,
                academic_year=academic_year,
                is_active=True,
            ).values_list("grade_id", flat=True)
            self.fields["grade"].queryset = Grade.objects.filter(
                school=school,
                is_active=True,
                id__in=configured_grade_ids,
            ).order_by("order", "name")
            self.fields["section"].queryset = Section.objects.filter(
                academic_year=academic_year,
                branch__school=school,
                is_active=True,
            ).select_related("grade").order_by("grade__order", "name")
        else:
            self.fields["grade"].queryset = Grade.objects.none()
            self.fields["section"].queryset = Section.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        grade = cleaned_data.get("grade")
        section = cleaned_data.get("section")
        if not grade or not self.school or not self.academic_year:
            return cleaned_data
        if not GradeFee.objects.filter(
            school=self.school,
            academic_year=self.academic_year,
            grade=grade,
            is_active=True,
        ).exists():
            self.add_error("grade", "هذا الصف غير مهيأ للعام الدراسي الحالي.")
            return cleaned_data

        valid_sections = Section.objects.filter(
            academic_year=self.academic_year,
            branch__school=self.school,
            grade=grade,
            is_active=True,
        )
        if section and not valid_sections.filter(pk=section.pk).exists():
            self.add_error("section", "الشعبة المختارة لا تتبع هذا الصف أو العام الدراسي.")
        elif not section and valid_sections.count() == 1:
            cleaned_data["section"] = valid_sections.first()
        elif not section and valid_sections.count() > 1:
            self.add_error("section", "اختر الشعبة لأن هذا الصف مقسم إلى أكثر من شعبة.")
        elif not section and not valid_sections.exists():
            self.add_error("section", "أضف شعبة واحدة على الأقل للصف قبل تسجيل طالب.")
        return cleaned_data

    def clean_guardian_identity_number(self):
        value = normalize_identifier(self.cleaned_data.get("guardian_identity_number") or "")
        if not value:
            raise forms.ValidationError("أدخل الرقم الوطني أو الشخصي لولي الأمر.")
        return value
