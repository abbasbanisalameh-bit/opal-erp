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
            "password": forms.PasswordInput(render_value=True, attrs={"class": "form-control"}),
            "client_secret": forms.PasswordInput(render_value=True, attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")


class OpenEMISImportForm(forms.Form):
    payload = forms.JSONField(
        label="بيانات OpenEMIS بصيغة JSON",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 18, "dir": "ltr"}),
        help_text="يُستخدم للاستيراد المرحلي أو لاختبار محول الوزارة دون إنشاء أي نموذج طالب مكرر.",
    )
