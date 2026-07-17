from django import forms

from .models import TimeSlot, TimetableEntry


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
