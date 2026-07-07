from django import forms
from django.contrib.auth.models import User
from .models import UserProfile

class UserProfileForm(forms.ModelForm):
    email = forms.EmailField(label="البريد الإلكتروني", required=False)
    first_name = forms.CharField(label="الاسم الأول", required=False)
    last_name = forms.CharField(label="اسم العائلة", required=False)

    class Meta:
        model = UserProfile
        fields = ["full_name", "phone", "photo"]
        labels = {
            "full_name": "الاسم الظاهر في النظام",
            "phone": "رقم الهاتف",
            "photo": "الصورة الشخصية",
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields["email"].initial = self.user.email
            self.fields["first_name"].initial = self.user.first_name
            self.fields["last_name"].initial = self.user.last_name

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user:
            self.user.email = self.cleaned_data.get("email", "")
            self.user.first_name = self.cleaned_data.get("first_name", "")
            self.user.last_name = self.cleaned_data.get("last_name", "")
            if commit:
                self.user.save()
        if commit:
            profile.save()
        return profile
