from django import forms

from .models import ClassCoverage, SchoolDayEvent, SchoolScheduleSettings, TeacherAbsence, TimeSlot, TimetableEntry


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "form-check-input" if getattr(field.widget, "input_type", "") == "checkbox" else "form-control"
            field.widget.attrs.setdefault("class", css)


class TimeSlotForm(StyledModelForm):
    class Meta:
        model = TimeSlot
        fields = ["name", "start_time", "end_time", "order", "is_active"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }


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
        widget=forms.CheckboxSelectMultiple, initial=["thursday", "friday"],
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
        initial=["saturday", "sunday", "monday", "tuesday", "wednesday"],
    )

    class Meta:
        model = SchoolDayEvent
        fields = ["name", "event_type", "start_time", "end_time", "days", "order", "is_active"]
        widgets = {"start_time": forms.TimeInput(attrs={"type": "time"}), "end_time": forms.TimeInput(attrs={"type": "time"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["days"] = [item.strip() for item in self.instance.days.split(",") if item.strip()]

    def clean_days(self):
        return ",".join(self.cleaned_data["days"])


class TeacherAbsenceForm(StyledModelForm):
    class Meta:
        model = TeacherAbsence
        fields = ["teacher", "date", "reason"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}


class CoverageAssignmentForm(StyledModelForm):
    class Meta:
        model = ClassCoverage
        fields = ["substitute_teacher"]
