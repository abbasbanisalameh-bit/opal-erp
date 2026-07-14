from django.contrib import admin
from .models import (
    Module,
    Task,
    Release,
    Milestone,
    Idea,
    Decision,
    Bug,
)


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "status", "progress", "version", "priority")
    list_filter = ("category", "status")
    search_fields = ("name", "description")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "status", "progress", "created_at")
    list_filter = ("status", "module")
    search_fields = ("title", "description")


@admin.register(Release)
class ReleaseAdmin(admin.ModelAdmin):
    list_display = ("version", "title", "planned_date", "released")
    list_filter = ("released",)
    search_fields = ("version", "title")


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ("title", "version", "progress", "completed")
    list_filter = ("completed", "version")


@admin.register(Idea)
class IdeaAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status", "priority")
    list_filter = ("status", "category")


@admin.register(Decision)
class DecisionAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "created_at")
    list_filter = ("status",)


@admin.register(Bug)
class BugAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "severity", "status")
    list_filter = ("severity", "status")
