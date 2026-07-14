from django import forms
from .models import Branch, School

class SchoolSettingsForm(forms.ModelForm):
    class Meta:
        model = School
        fields = ["name", "official_name", "logo", "phone", "email", "address", "is_active"]
        labels = {
            "name": "اسم المدرسة",
            "official_name": "الاسم الرسمي",
            "logo": "شعار المدرسة",
            "phone": "الهاتف",
            "email": "البريد الإلكتروني",
            "address": "العنوان",
            "is_active": "فعالة",
        }


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ["name", "phone", "address", "is_main", "is_active"]
        labels = {
            "name": "اسم الفرع",
            "phone": "هاتف الفرع",
            "address": "عنوان الفرع",
            "is_main": "الفرع الرئيسي",
            "is_active": "فعال",
        }
        widgets = {"address": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, school=None, **kwargs):
        self.school = school
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
