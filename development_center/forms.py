from django import forms
from .models import (
    Module,
    Task,
    Release,
    Milestone,
    Idea,
    Decision,
    Bug,
)


class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = "__all__"


class ReleaseForm(forms.ModelForm):
    class Meta:
        model = Release
        fields = "__all__"


class MilestoneForm(forms.ModelForm):
    class Meta:
        model = Milestone
        fields = "__all__"


class IdeaForm(forms.ModelForm):
    class Meta:
        model = Idea
        fields = "__all__"


class DecisionForm(forms.ModelForm):
    class Meta:
        model = Decision
        fields = "__all__"


class BugForm(forms.ModelForm):
    class Meta:
        model = Bug
        fields = "__all__"


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = "__all__"
