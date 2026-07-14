from django import forms
from django.forms import modelformset_factory

from .models import RolePermissionRule


class WorkflowActionForm(forms.Form):
    ACTION_CHOICES = [
        ("review", "بدء المراجعة"),
        ("approve", "اعتماد"),
        ("reject", "رفض"),
        ("return", "إعادة للاستكمال"),
        ("archive", "أرشفة"),
        ("comment", "إضافة تعليق"),
    ]
    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.Select(attrs={"class": "form-select"}))
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))

    def clean(self):
        data = super().clean()
        if data.get("action") in {"reject", "return"} and not (data.get("note") or "").strip():
            self.add_error("note", "سبب الرفض أو الإعادة مطلوب.")
        return data

RolePermissionFormSet = modelformset_factory(
    RolePermissionRule,
    fields=["can_view", "can_create", "can_update", "can_approve", "can_export", "is_active"],
    extra=0,
    widgets={
        "can_view": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        "can_create": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        "can_update": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        "can_approve": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        "can_export": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
    },
)
