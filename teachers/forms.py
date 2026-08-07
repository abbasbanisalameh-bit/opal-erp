from django import forms
from django.utils import timezone
from core.finance_constants import ACTIVE_PAYMENT_METHOD_CHOICES

from .models import Homework, Teacher, TeacherAdvance, TeacherAssignment, TeacherPayroll


class DateInput(forms.DateInput):
    input_type = "date"


class TeacherForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = [
            "employee_number", "full_name", "national_id", "gender", "birth_date",
            "phone", "email", "address", "specialization", "qualification",
            "hire_date", "school", "branch", "monthly_salary", "photo",
        ]
        widgets = {
            "birth_date": DateInput(), "hire_date": DateInput(),
            "address": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "employee_number": "الرقم الوظيفي", "full_name": "اسم المعلم الكامل",
            "national_id": "الرقم الوطني", "gender": "الجنس", "birth_date": "تاريخ الميلاد",
            "phone": "الهاتف", "email": "البريد الإلكتروني", "address": "العنوان",
            "specialization": "التخصص", "qualification": "المؤهل", "hire_date": "تاريخ التعيين",
            "school": "المدرسة", "branch": "الفرع", "monthly_salary": "الراتب الشهري",
            "photo": "الصورة",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"
        self.fields["photo"].widget.attrs["accept"] = "image/*"
        self.fields["photo"].help_text = "الحد الأقصى لحجم الصورة: 1 ميجابايت."

    def clean_national_id(self):
        value = (self.cleaned_data.get("national_id") or "").strip()
        if value and Teacher.objects.filter(national_id__iexact=value).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("الرقم الوطني مرتبط بمعلم آخر. افتح ملفه بدل إنشاء سجل مكرر.")
        return value


class TeacherAssignmentForm(forms.ModelForm):
    weekly_teaching_load = forms.IntegerField(
        label="النصاب الأسبوعي المعتمد",
        min_value=1,
        max_value=60,
        help_text="الحد الأعلى لجميع حصص المعلم من الأحد إلى الخميس.",
    )
    free_period_policy = forms.ChoiceField(
        label="سياسة فراغ المعلم",
        choices=Teacher.FREE_PERIOD_POLICIES,
    )
    daily_free_periods = forms.IntegerField(
        label="الفراغ اليومي المطلوب",
        min_value=0,
        max_value=3,
        required=False,
        help_text="يستخدم فقط عند اختيار حد أدنى يومي.",
    )
    weekly_free_periods = forms.IntegerField(
        label="الفراغ الأسبوعي المطلوب",
        min_value=0,
        max_value=20,
        required=False,
        help_text="يستخدم فقط عند اختيار عدد أسبوعي.",
    )

    class Meta:
        model = TeacherAssignment
        fields = ["academic_year", "section", "subject", "is_primary", "is_active"]
        labels = {
            "academic_year": "العام الدراسي", "section": "الشعبة", "subject": "المادة والخطة",
            "is_primary": "المعلم الأساسي", "is_active": "تكليف فعال",
        }

    def __init__(self, *args, teacher=None, **kwargs):
        self.teacher = teacher or getattr(kwargs.get("instance"), "teacher", None)
        super().__init__(*args, **kwargs)
        if self.teacher:
            school = self.teacher.school
            self.fields["academic_year"].queryset = school.academic_years.filter(is_closed=False)
            self.fields["section"].queryset = self.fields["section"].queryset.filter(
                branch__school=school,
                academic_year__is_closed=False,
            )
            self.fields["subject"].queryset = self.fields["subject"].queryset.filter(academic_year__school=school, academic_year__is_closed=False, is_active=True).select_related("grade", "academic_year")
            self.initial.setdefault("weekly_teaching_load", self.teacher.weekly_teaching_load)
            self.initial.setdefault("free_period_policy", self.teacher.free_period_policy)
            self.initial.setdefault("daily_free_periods", self.teacher.daily_free_periods)
            self.initial.setdefault("weekly_free_periods", self.teacher.weekly_free_periods)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

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

        plan = subject if subject and subject.is_active else None
        if year and section and subject:
            if subject.academic_year_id != year.pk or subject.grade_id != section.grade_id:
                self.add_error("subject", "المادة لا تتبع العام وصف الشعبة المحددين. اخترها من خطة العام نفسها.")
                plan = None

        load = cleaned.get("weekly_teaching_load")
        policy = cleaned.get("free_period_policy")
        daily_free = cleaned.get("daily_free_periods") or 0
        weekly_free = cleaned.get("weekly_free_periods") or 0
        if policy == "daily":
            if not 1 <= daily_free <= 3:
                self.add_error("daily_free_periods", "حدد من حصة إلى ثلاث حصص فراغ يوميًا.")
            cleaned["weekly_free_periods"] = 0
        elif policy == "weekly":
            if not 1 <= weekly_free <= 20:
                self.add_error("weekly_free_periods", "حدد عدد الفراغ الأسبوعي من 1 إلى 20.")
            cleaned["daily_free_periods"] = 0
        else:
            cleaned["daily_free_periods"] = 0
            cleaned["weekly_free_periods"] = 0

        if year and plan and load:
            total = 0
            existing = TeacherAssignment.objects.filter(
                teacher=teacher,
                academic_year=year,
                is_active=True,
            ).select_related("section__grade", "subject")
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            for assignment in existing:
                total += assignment.subject.weekly_periods
            if cleaned.get("is_active", True):
                total += plan.weekly_periods
            if total > load:
                self.add_error(
                    "weekly_teaching_load",
                    f"لا يمكن حفظ التكليف؛ ستصبح الحصص المسندة {total} بينما النصاب المعتمد {load}.",
                )
        return cleaned

    def save_teacher_workload(self):
        if not self.teacher:
            return
        self.teacher.weekly_teaching_load = self.cleaned_data["weekly_teaching_load"]
        self.teacher.free_period_policy = self.cleaned_data["free_period_policy"]
        self.teacher.daily_free_periods = self.cleaned_data.get("daily_free_periods") or 0
        self.teacher.weekly_free_periods = self.cleaned_data.get("weekly_free_periods") or 0
        self.teacher.save(update_fields=[
            "weekly_teaching_load", "free_period_policy",
            "daily_free_periods", "weekly_free_periods",
        ])


class TeacherAccountCreateForm(forms.Form):
    username = forms.CharField(
        required=False,
        max_length=150,
        label="اسم المستخدم",
        help_text="اتركه فارغًا ليتم توليده من الرقم الوظيفي.",
        widget=forms.TextInput(attrs={"class": "form-control", "dir": "ltr", "autocomplete": "off"}),
    )


class HomeworkForm(forms.ModelForm):
    class Meta:
        model = Homework
        fields = ["title", "description", "assigned_date", "due_date", "attachment", "is_active"]
        widgets = {
            "assigned_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "attachment": forms.ClearableFileInput(attrs={"accept": ".pdf,.doc,.docx,.jpg,.jpeg,.png"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control",
            )


class TeacherTerminationForm(forms.Form):
    end_date = forms.DateField(label="تاريخ انتهاء الخدمة", widget=DateInput())
    end_reason = forms.CharField(label="سبب انتهاء الخدمة", max_length=200, widget=forms.Textarea(attrs={"rows": 3}))
    confirmation = forms.CharField(label="التأكيد", help_text="اكتب: إنهاء خدمة المعلم")

    def __init__(self, *args, teacher=None, **kwargs):
        self.teacher = teacher
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_end_date(self):
        value = self.cleaned_data["end_date"]
        if self.teacher and self.teacher.hire_date and value < self.teacher.hire_date:
            raise forms.ValidationError("تاريخ انتهاء الخدمة لا يمكن أن يسبق تاريخ التعيين.")
        if value > timezone.localdate():
            raise forms.ValidationError("لا يمكن تنفيذ إنهاء الخدمة بتاريخ مستقبلي.")
        return value

    def clean_confirmation(self):
        value = self.cleaned_data["confirmation"].strip()
        if value != "إنهاء خدمة المعلم":
            raise forms.ValidationError("اكتب العبارة: إنهاء خدمة المعلم")
        return value


class PayrollPeriodForm(forms.Form):
    period = forms.DateField(
        label="شهر الراتب",
        input_formats=["%Y-%m"],
        widget=forms.DateInput(format="%Y-%m", attrs={"type": "month", "class": "form-control"}),
    )


class PayrollAdjustmentForm(forms.ModelForm):
    payment_method = forms.ChoiceField(label="طريقة الدفع", choices=[("", "— لم يدفع بعد —"), *ACTIVE_PAYMENT_METHOD_CHOICES], required=False)

    class Meta:
        model = TeacherPayroll
        fields = ["manager_increase", "other_deduction", "payment_method", "payment_reference", "correction_note"]
        widgets = {"correction_note": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class AdvanceRequestForm(forms.ModelForm):
    class Meta:
        model = TeacherAdvance
        fields = ["amount"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount"].widget.attrs.update({"class": "form-control", "min": "0.01", "step": "0.01"})


class AdvanceDisbursementForm(forms.Form):
    payment_method = forms.ChoiceField(label="طريقة الصرف", choices=ACTIVE_PAYMENT_METHOD_CHOICES)
    reference = forms.CharField(label="المرجع", max_length=100, required=False)
    admin_note = forms.CharField(label="ملاحظة الإدارة", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select" if isinstance(field.widget, forms.Select) else "form-control")
