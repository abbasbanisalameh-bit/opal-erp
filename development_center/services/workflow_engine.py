from django.utils import timezone
from development_center.models import Task, Module, Sprint, Release, Notification, ActivityLog


def set_if_exists(obj, field, value):
    if hasattr(obj, field):
        setattr(obj, field, value)
        obj.save(update_fields=[field])


def safe_activity(task, old_status, old_progress):
    fields = {f.name for f in ActivityLog._meta.fields}
    data = {}
    if "action" in fields: data["action"] = "update"
    if "title" in fields: data["title"] = f"تحديث تلقائي: {task.title}"
    if "description" in fields:
        data["description"] = f"{old_status} → {task.status} | {old_progress}% → {task.progress}%"
    if "module" in fields: data["module"] = task.module
    if "task" in fields: data["task"] = task
    ActivityLog.objects.create(**data)


def normalize_tasks():
    for task in Task.objects.all():
        old_status = task.status
        old_progress = task.progress or 0

        if task.progress >= 100:
            task.progress = 100
            task.status = "done"
        elif task.progress <= 0:
            task.progress = 0
            task.status = "todo"
        elif task.status not in ["review"]:
            task.status = "doing"

        if old_status != task.status or old_progress != task.progress:
            task.save(update_fields=["status", "progress"])
            safe_activity(task, old_status, old_progress)


def recalc_sprints():
    for sprint in Sprint.objects.prefetch_related("tasks").all():
        tasks = sprint.tasks.all()
        total = tasks.count()

        if not total:
            sprint.status = "planned"
        else:
            avg = round(sum([t.progress or 0 for t in tasks]) / total)
            if avg >= 100:
                sprint.status = "completed"
            elif avg > 0:
                sprint.status = "active"
            else:
                sprint.status = "planned"

            set_if_exists(sprint, "progress", avg)

        sprint.save(update_fields=["status"])


def recalc_modules():
    for module in Module.objects.all():
        tasks = Task.objects.filter(module=module)
        total = tasks.count()
        avg = round(sum([t.progress or 0 for t in tasks]) / total) if total else 0
        set_if_exists(module, "progress", avg)


def recalc_releases():
    for release in Release.objects.all():
        tasks = Task.objects.filter(release=release)
        total = tasks.count()
        avg = round(sum([t.progress or 0 for t in tasks]) / total) if total else 0
        set_if_exists(release, "progress", avg)


def generate_overdue_notifications():
    today = timezone.localdate()
    created = 0

    for task in Task.objects.filter(due_date__lt=today).exclude(status="done"):
        title = f"مهمة متأخرة: {task.title}"
        if not Notification.objects.filter(title=title, is_read=False).exists():
            Notification.objects.create(
                title=title,
                message=f"المهمة متأخرة منذ {task.due_date}",
                level="danger",
                url=f"/development/tasks/{task.id}/",
            )
            created += 1

    return created


def run_workflow_engine():
    normalize_tasks()
    recalc_sprints()
    recalc_modules()
    recalc_releases()
    overdue = generate_overdue_notifications()
    return {"overdue_notifications": overdue}

def sync_after_task_change(task=None, user=None):
    return run_workflow_engine()

def update_task_status(task, status=None, progress=None, user=None):
    if status is not None:
        task.status = status

    if progress is not None:
        task.progress = progress

    task.save()
    sync_after_task_change(task=task, user=user)
    return task
