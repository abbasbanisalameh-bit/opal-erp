from django import forms
from .models import Module


class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = [
            "name",
            "category",
            "description",
            "version",
            "progress",
            "priority",
            "status",
            "is_active",
        ]
