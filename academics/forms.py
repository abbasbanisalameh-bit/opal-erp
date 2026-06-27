from django import forms
from .models import StudentRecord, Guardian, Grade, Section


class StudentRecordForm(forms.ModelForm):
    class Meta:
        model = StudentRecord
        fields = [
            "full_name",
            "national_id",
            "father_name",
            "gender",
            "blood_type",
            "address",
            "medical_notes",
            "photo",
            "is_active",
        ]

        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "اسم الطالب الكامل"}),
            "national_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "الرقم الوطني"}),
            "father_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "اسم ولي الأمر / الأب"}),
            "gender": forms.Select(attrs={"class": "form-control"}),
            "blood_type": forms.TextInput(attrs={"class": "form-control", "placeholder": "فصيلة الدم"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "العنوان"}),
            "medical_notes": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "ملاحظات صحية"}),
            "photo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class StudentAdmissionForm(forms.Form):
    full_name = forms.CharField(label="اسم الطالب الكامل", widget=forms.TextInput(attrs={"class": "form-control"}))
    national_id = forms.CharField(label="الرقم الوطني", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    father_name = forms.CharField(label="اسم ولي الأمر / الأب", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    gender = forms.ChoiceField(label="الجنس", choices=StudentRecord.GENDER_CHOICES, widget=forms.Select(attrs={"class": "form-control"}))
    blood_type = forms.CharField(label="فصيلة الدم", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    address = forms.CharField(label="العنوان", required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))
    medical_notes = forms.CharField(label="ملاحظات صحية", required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))
    photo = forms.ImageField(label="صورة الطالب", required=False, widget=forms.ClearableFileInput(attrs={"class": "form-control"}))

    guardian_name = forms.CharField(label="اسم ولي الأمر", widget=forms.TextInput(attrs={"class": "form-control"}))
    guardian_relation = forms.ChoiceField(label="صلة القرابة", choices=Guardian.RELATION_CHOICES, widget=forms.Select(attrs={"class": "form-control"}))
    guardian_phone = forms.CharField(label="هاتف ولي الأمر", widget=forms.TextInput(attrs={"class": "form-control"}))
    guardian_job = forms.CharField(label="مهنة ولي الأمر", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))

    grade = forms.ModelChoiceField(label="الصف", queryset=Grade.objects.all(), widget=forms.Select(attrs={"class": "form-control"}))
    section = forms.ModelChoiceField(label="الشعبة", queryset=Section.objects.all(), required=False, widget=forms.Select(attrs={"class": "form-control"}))
