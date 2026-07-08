from django import forms
from .models import OpenEMISSettings


class OpenEMISSettingsForm(forms.ModelForm):
    class Meta:
        model = OpenEMISSettings
        fields = [
            "is_enabled", "base_url", "username", "password", "client_id", "client_secret",
            "auto_push_registration", "auto_pull_student", "sync_guardians", "notes",
        ]
        widgets = {
            "password": forms.PasswordInput(render_value=True),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
