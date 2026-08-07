from django import forms
from django.contrib.auth.models import User
from django.forms import modelformset_factory

from teachers.models import Teacher

from .models import BroadcastMessage, FeedbackTicket, RolePermissionRule


class WorkflowActionForm(forms.Form):
    """Compatibility form for internal workflows still used by other modules."""

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


class FeedbackTicketForm(forms.ModelForm):
    """Simple user message form; monthly evaluation has its own workflow."""

    class Meta:
        model = FeedbackTicket
        fields = ["kind", "message"]
        widgets = {
            "kind": forms.Select(attrs={"class": "form-select"}),
            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": "اكتب تفاصيل الشكوى أو الاقتراح بوضوح...",
                }
            ),
        }


class FeedbackManagementForm(forms.ModelForm):
    class Meta:
        model = FeedbackTicket
        fields = ["status", "assigned_to", "response"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
            "response": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.filter(is_active=True, is_staff=True).order_by(
            "first_name", "username"
        )
        self.fields["assigned_to"].required = False

    def clean(self):
        data = super().clean()
        if data.get("status") in {"resolved", "closed"} and not (data.get("response") or "").strip():
            self.add_error("response", "رد الإدارة مطلوب عند إغلاق الشكوى أو الاقتراح.")
        return data


class BroadcastMessageForm(forms.ModelForm):
    class Meta:
        model = BroadcastMessage
        fields = ["message_type", "audience", "specific_teacher", "title", "message"]
        widgets = {
            "message_type": forms.Select(attrs={"class": "form-select"}),
            "audience": forms.Select(attrs={"class": "form-select"}),
            "specific_teacher": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-control", "maxlength": 180}),
            "message": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        teachers = Teacher.objects.filter(is_active=True).select_related("user").exclude(user=None)
        if school is not None:
            teachers = teachers.filter(school=school)
        self.fields["specific_teacher"].queryset = teachers.order_by("full_name")
        self.fields["specific_teacher"].required = False

    def clean(self):
        data = super().clean()
        message_type = data.get("message_type")
        teacher = data.get("specific_teacher")
        if message_type == "teacher_alert":
            if not teacher:
                self.add_error("specific_teacher", "اختر المعلم الذي سيستقبل التنبيه.")
            data["audience"] = "teachers"
        else:
            data["specific_teacher"] = None
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
