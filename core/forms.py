from django import forms
from .models import School

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
