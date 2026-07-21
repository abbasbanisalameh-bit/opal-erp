"""Unified read/workflow entry points for OPAL Development Center.

This module preserves the current models, templates and business rules while
keeping query/context construction outside HTTP views.
"""
from django.utils import timezone

from .models import Bug, Idea, Module, Notification, Release, Sprint, Task


def build_development_dashboard_context():
    modules = Module.objects.all()
    total = modules.count()
    tasks_total = Task.objects.count()
    tasks_done = Task.objects.filter(status="done").count()
    return {
        "modules": modules.order_by("-progress"),
        "latest_tasks": Task.objects.select_related("module", "release").order_by("-id")[:8],
        "latest_bugs": Bug.objects.select_related("module").order_by("-id")[:8],
        "latest_releases": Release.objects.order_by("-id")[:5],
        "total": total,
        "completed": modules.filter(status="completed").count(),
        "development": modules.filter(status="development").count(),
        "planned": modules.filter(status="planned").count(),
        "progress": round(sum(module.progress for module in modules) / total) if total else 0,
        "overall_progress": round((tasks_done / tasks_total) * 100) if tasks_total else 0,
        "tasks_count": tasks_total,
        "tasks_done": tasks_done,
        "bugs_count": Bug.objects.count(),
        "ideas_count": Idea.objects.count(),
        "releases_count": Release.objects.count(),
    }


def build_tasks_board_context(filters):
    tasks = Task.objects.select_related("module", "release", "sprint").all()
    module_id = filters.get("module")
    release_id = filters.get("release")
    sprint_id = filters.get("sprint")
    priority = filters.get("priority")
    if module_id:
        tasks = tasks.filter(module_id=module_id)
    if release_id:
        tasks = tasks.filter(release_id=release_id)
    if sprint_id:
        tasks = tasks.filter(sprint_id=sprint_id)
    if priority:
        tasks = tasks.filter(priority=priority)
    return {
        "todo": tasks.filter(status="todo"),
        "doing": tasks.filter(status="doing"),
        "review": tasks.filter(status="review"),
        "done": tasks.filter(status="done"),
        "modules": Module.objects.all(),
        "releases": Release.objects.all(),
        "sprints": Sprint.objects.all(),
        "selected_module": module_id,
        "selected_release": release_id,
        "selected_sprint": sprint_id,
        "selected_priority": priority,
    }


def build_roadmap_context():
    rows = []
    releases = Release.objects.all().order_by("planned_date", "id")
    for release in releases:
        milestones = release.milestone_set.all().order_by("target_date")
        total = milestones.count()
        completed = milestones.filter(completed=True).count()
        rows.append({
            "release": release,
            "milestones": milestones,
            "total": total,
            "completed": completed,
            "progress": round(completed / total * 100) if total else 0,
        })
    return {"roadmap": rows}


def build_sprint_detail_context(sprint):
    tasks = sprint.tasks.all()
    total = tasks.count()
    done = tasks.filter(status="done").count()
    today = timezone.localdate()
    return {
        "sprint": sprint,
        "tasks": tasks,
        "total": total,
        "done": done,
        "doing": tasks.filter(status="doing").count(),
        "review": tasks.filter(status="review").count(),
        "todo": tasks.filter(status="todo").count(),
        "remaining": total - done,
        "progress": round((done / total) * 100) if total else 0,
        "days_left": (sprint.end_date - today).days if sprint.end_date else None,
        "overdue_tasks": tasks.filter(due_date__lt=today).exclude(status="done"),
    }


def build_notifications_context(user):
    return {
        "notifications": Notification.objects.filter(user=user).order_by("-created_at")[:200]
    }
