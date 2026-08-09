from datetime import time

from django import forms

from .models import (
    BiometricDevice, ClassCoverage, SchoolDayEvent, SchoolScheduleSettings, TeacherAbsence,
    TeacherBiometricIdentity, TimeSlot, TimetableEntry,
)


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "form-check-input" if getattr(field.widget, "input_type", "") == "checkbox" else "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs.setdefault("class", css)


class TimeSlotForm(StyledModelForm):
    class Meta:
        model = TimeSlot
        fields = ["name", "start_time", "end_time", "order", "is_active"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }
        labels = {"name": "اسم الحصة", "start_time": "وقت البداية", "end_time": "وقت النهاية", "order": "الترتيب", "is_active": "فعالة"}


class TimetableEntryForm(StyledModelForm):
    class Meta:
        model = TimetableEntry
        fields = [
            "academic_year",
            "section",
            "subject",
            "teacher",
            "day",
            "time_slot",
            "room",
            "is_active",
        ]
        labels = {
            "academic_year": "العام الدراسي", "section": "الشعبة", "subject": "المادة",
            "teacher": "المعلم", "day": "اليوم", "time_slot": "الحصة الزمنية",
            "room": "الغرفة", "is_active": "فعالة",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["academic_year"].queryset = self.fields["academic_year"].queryset.filter(is_closed=False)
        self.fields["section"].queryset = self.fields["section"].queryset.filter(
            is_active=True,
            academic_year__is_closed=False,
        )


class SchoolScheduleSettingsForm(StyledModelForm):
    weekend_days = forms.MultipleChoiceField(
        label="أيام العطلة", choices=TimetableEntry.DAYS,
        widget=forms.CheckboxSelectMultiple, initial=["friday", "saturday"],
    )

    class Meta:
        model = SchoolScheduleSettings
        fields = ["weekend_days", "alert_minutes_before_end"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["weekend_days"] = list(self.instance.weekend_day_codes)

    def clean_weekend_days(self):
        return ",".join(self.cleaned_data["weekend_days"])


class SchoolDayEventForm(StyledModelForm):
    days = forms.MultipleChoiceField(
        label="أيام التطبيق", choices=TimetableEntry.DAYS,
        widget=forms.CheckboxSelectMultiple,
        initial=["sunday", "monday", "tuesday", "wednesday", "thursday"],
    )

    class Meta:
        model = SchoolDayEvent
        fields = [
            "name", "event_type", "placement_mode", "duration_minutes",
            "start_time", "end_time", "days", "sections", "order", "is_active",
        ]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "sections": forms.CheckboxSelectMultiple,
        }
        labels = {
            "sections": "الشعب التابعة للاستراحة",
            "duration_minutes": "مدة الاستراحة بالدقائق",
        }
        help_texts = {
            "sections": "اختر مجموعة الشعب التي تخرج في هذه الاستراحة. لا يوجد إعداد للسعة أو تعدد الساحات.",
            "placement_mode": "في الوضع الذكي يضع النظام الاستراحة بعد ساعتين من بداية اليوم وقبل ساعتين من نهايته.",
        }

    def __init__(self, *args, school=None, **kwargs):
        self.school = school or getattr(kwargs.get("instance"), "school", None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["days"] = list(self.instance.day_codes)
            if self.instance.event_type == "break" and not self.instance.duration_minutes:
                self.initial["duration_minutes"] = self.instance.effective_duration_minutes
        if self.school:
            self.fields["sections"].queryset = self.fields["sections"].queryset.filter(
                branch__school=self.school,
                is_active=True,
                academic_year__is_closed=False,
            ).select_related("grade", "academic_year").order_by(
                "academic_year__start_date", "grade__order", "name"
            )
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                continue
            field.widget.attrs.setdefault(
                "class",
                "form-check-input" if isinstance(field.widget, forms.CheckboxInput)
                else "form-select" if isinstance(field.widget, forms.Select)
                else "form-control",
            )

    def clean_days(self):
        return ",".join(self.cleaned_data["days"])

    def clean(self):
        cleaned = super().clean()
        event_type = cleaned.get("event_type")
        placement = cleaned.get("placement_mode")
        sections = cleaned.get("sections")
        days = set((cleaned.get("days") or "").split(","))
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        duration = cleaned.get("duration_minutes")
        if event_type == "break" and not sections:
            self.add_error("sections", "اختر مجموعة الشعب التابعة لهذه الاستراحة.")
        if event_type == "break" and not duration:
            self.add_error("duration_minutes", "حدد مدة الاستراحة بالدقائق.")
        if event_type == "break" and placement == "smart":
            cleaned["start_time"] = None
            cleaned["end_time"] = None
        elif event_type == "break" and placement == "fixed":
            if not start:
                self.add_error("start_time", "حدد وقت بداية الاستراحة الثابتة.")
            elif duration:
                end_minutes = start.hour * 60 + start.minute + duration
                if end_minutes >= 24 * 60:
                    self.add_error("start_time", "وقت الاستراحة ومدتها يتجاوزان نهاية اليوم.")
                else:
                    cleaned["end_time"] = time(end_minutes // 60, end_minutes % 60)
                    end = cleaned["end_time"]
        if self.school and event_type == "break" and placement == "fixed" and start and end:
            overlapping = SchoolDayEvent.objects.filter(
                school=self.school,
                event_type="break",
                is_active=True,
                placement_mode="fixed",
                start_time__lt=end,
                end_time__gt=start,
            )
            if self.instance and self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            for other in overlapping:
                if days & other.day_codes:
                    self.add_error(None, "لا يمكن تداخل استراحتين لأن المدرسة تستخدم ساحة واحدة.")
                    break
        if self.school and event_type == "break" and sections:
            selected_ids = set(sections.values_list("pk", flat=True))
            other_breaks = SchoolDayEvent.objects.filter(
                school=self.school,
                event_type="break",
                is_active=True,
                sections__in=selected_ids,
            ).distinct()
            if self.instance and self.instance.pk:
                other_breaks = other_breaks.exclude(pk=self.instance.pk)
            for other in other_breaks:
                if days & other.day_codes:
                    self.add_error("sections", f"بعض الشعب موجودة مسبقًا في الاستراحة «{other.name}» في الأيام نفسها.")
                    break
        return cleaned


class TeacherAbsenceForm(StyledModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["attendance_status"].choices = [
            choice for choice in TeacherAbsence.ATTENDANCE_STATUSES if choice[0] != "present"
        ]

    class Meta:
        model = TeacherAbsence
        fields = [
            "teacher",
            "date",
            "attendance_status",
            "arrival_time",
            "departure_time",
            "absence_type",
            "reason",
            "is_approved",
            "payroll_approved",
            "deduction_amount",
            "payroll_notes",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "arrival_time": forms.TimeInput(attrs={"type": "time"}),
            "departure_time": forms.TimeInput(attrs={"type": "time"}),
        }
        labels = {
            "teacher": "المعلم",
            "date": "التاريخ",
            "attendance_status": "حالة الدوام",
            "reason": "السبب أو الملاحظة",
        }


class CoverageAssignmentForm(StyledModelForm):
    class Meta:
        model = ClassCoverage
        fields = ["substitute_teacher"]


class BiometricDeviceForm(StyledModelForm):
    class Meta:
        model = BiometricDevice
        fields = ["name", "device_code", "vendor", "serial_number", "branch", "timezone_name", "is_active"]
        labels = {
            "name": "اسم الجهاز",
            "device_code": "رمز الجهاز",
            "vendor": "الشركة",
            "serial_number": "الرقم التسلسلي",
            "branch": "الفرع",
            "timezone_name": "المنطقة الزمنية",
            "is_active": "فعال",
        }

    def __init__(self, *args, school=None, **kwargs):
        self.school = school
        super().__init__(*args, **kwargs)
        if self.school:
            self.fields["branch"].queryset = self.fields["branch"].queryset.filter(school=self.school)


class TeacherBiometricIdentityForm(StyledModelForm):
    class Meta:
        model = TeacherBiometricIdentity
        fields = ["device", "teacher", "device_user_id", "is_active"]
        labels = {
            "device": "جهاز البصمة",
            "teacher": "المعلم",
            "device_user_id": "رقم/معرف المعلم داخل الجهاز",
            "is_active": "فعال",
        }

    def __init__(self, *args, school=None, **kwargs):
        self.school = school
        super().__init__(*args, **kwargs)
        if self.school:
            self.fields["device"].queryset = self.fields["device"].queryset.filter(school=self.school, is_active=True)
            self.fields["teacher"].queryset = self.fields["teacher"].queryset.filter(school=self.school, is_active=True)
