from django import forms

from .models import Attendance


class AttendanceEditForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ["status"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
