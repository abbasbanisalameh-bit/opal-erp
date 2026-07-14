from django import forms

from .models import Attendance


class AttendanceEditForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ["status", "arrival_time", "departure_time", "excuse_reason", "notes"]
        widgets = {
            "arrival_time": forms.TimeInput(attrs={"type": "time"}),
            "departure_time": forms.TimeInput(attrs={"type": "time"}),
            "excuse_reason": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
