from django import forms
from .models import Module, Task, Release, Milestone, Idea, Decision, Bug, Sprint

STATUS_CHOICES_AR = [
    ("todo", "لم يبدأ"),
    ("doing", "قيد التنفيذ"),
    ("review", "قيد المراجعة"),
    ("done", "مكتملة"),
]


class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = "__all__"
        labels = {
            "name": "اسم الوحدة",
            "category": "التصنيف",
            "description": "الوصف",
            "version": "الإصدار المستهدف",
            "progress": "نسبة الإنجاز",
            "priority": "الأولوية",
            "status": "الحالة",
            "is_active": "نشطة؟",
        }


class ReleaseForm(forms.ModelForm):
    class Meta:
        model = Release
        fields = "__all__"
        labels = {
            "version": "رقم الإصدار",
            "title": "عنوان الإصدار",
            "description": "الوصف",
            "planned_date": "تاريخ الإصدار المخطط",
            "released": "تم الإصدار؟",
        }


class MilestoneForm(forms.ModelForm):
    class Meta:
        model = Milestone
        fields = "__all__"
        labels = {
            "title": "اسم المرحلة",
            "version": "الإصدار",
            "target_date": "التاريخ المستهدف",
            "progress": "نسبة الإنجاز",
            "completed": "مكتملة؟",
        }


class IdeaForm(forms.ModelForm):
    class Meta:
        model = Idea
        fields = "__all__"
        labels = {
            "title": "عنوان الفكرة",
            "description": "الوصف",
            "category": "التصنيف",
            "priority": "الأولوية",
            "status": "الحالة",
        }


class DecisionForm(forms.ModelForm):
    class Meta:
        model = Decision
        fields = "__all__"
        labels = {
            "title": "عنوان القرار",
            "decision": "نص القرار",
            "reason": "السبب",
            "impact": "الأثر",
            "status": "الحالة",
        }


class BugForm(forms.ModelForm):
    class Meta:
        model = Bug
        fields = "__all__"
        labels = {
            "title": "عنوان الخطأ",
            "description": "الوصف",
            "module": "الوحدة",
            "release": "الإصدار",
            "severity": "الخطورة",
            "status": "الحالة",
        }


class TaskForm(forms.ModelForm):
    status = forms.ChoiceField(label="الحالة", choices=STATUS_CHOICES_AR)

    class Meta:
        model = Task
        fields = "__all__"
        labels = {
            "module": "الوحدة",
            "release": "الإصدار",
            "sprint": "دورة التطوير",
            "title": "عنوان المهمة",
            "description": "الوصف",
            "status": "الحالة",
            "progress": "نسبة الإنجاز",
            "start_date": "تاريخ البداية",
            "due_date": "تاريخ النهاية",
            "depends_on": "يعتمد على",
        }
        widgets = {
            "depends_on": forms.CheckboxSelectMultiple,
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class SprintForm(forms.ModelForm):
    class Meta:
        model = Sprint
        fields = "__all__"
        labels = {
            "title": "اسم دورة التطوير",
            "goal": "هدف دورة التطوير",
            "start_date": "تاريخ البداية",
            "end_date": "تاريخ النهاية",
            "status": "الحالة",
        }
