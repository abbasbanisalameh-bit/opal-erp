from django import forms

from .models import Announcement


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ["title", "message", "announcement_type", "speed_seconds", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "maxlength": 200}),
            "message": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "announcement_type": forms.Select(attrs={"class": "form-select"}),
            "speed_seconds": forms.NumberInput(attrs={"class": "form-control", "min": 5, "max": 120}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_speed_seconds(self):
        value = self.cleaned_data["speed_seconds"]
        if not 5 <= value <= 120:
            raise forms.ValidationError("سرعة الإعلان يجب أن تكون بين 5 و120 ثانية.")
        return value
