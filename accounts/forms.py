from django import forms
from .models import Role, UserProfile


class UserProfileForm(forms.ModelForm):
    email = forms.EmailField(label="البريد الإلكتروني", required=False)
    first_name = forms.CharField(label="الاسم الأول", required=False)
    last_name = forms.CharField(label="الاسم الأخير", required=False)

    class Meta:
        model = UserProfile
        fields = ["full_name", "phone", "photo"]
        labels = {
            "full_name": "الاسم الظاهر في النظام",
            "phone": "رقم الهاتف",
            "photo": "الصورة الشخصية",
        }
        widgets = {
            "photo": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields["email"].initial = self.user.email
            self.fields["first_name"].initial = self.user.first_name
            self.fields["last_name"].initial = self.user.last_name
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user:
            self.user.email = self.cleaned_data.get("email", "")
            self.user.first_name = self.cleaned_data.get("first_name", "")
            self.user.last_name = self.cleaned_data.get("last_name", "")
            if commit:
                self.user.save(update_fields=["email", "first_name", "last_name"])
        if commit:
            profile.save()
        return profile


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ["code", "name", "description", "is_active"]
        labels = {
            "code": "رمز الدور",
            "name": "اسم الدور",
            "description": "الوصف",
            "is_active": "فعال",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-check-input"
                if isinstance(field.widget, forms.CheckboxInput)
                else "form-control"
            )
