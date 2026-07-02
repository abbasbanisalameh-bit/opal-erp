"""محرك سير العمل لمركز التطوير.

هذا الملف مسؤول عن مزامنة حالة المهام والنسب والإشعارات بعد أي تغيير.
تم تصميمه ليكون آمنًا مع signals حتى لا يدخل في حلقات حفظ متكررة.
"""
from dataclasses import dataclass
from typing import Optional

from django.utils import timezone

from development_center.models import ActivityLog, Module, Notification, Release, Sprint, Task

_ENGINE_RUNNING = False


@dataclass
class WorkflowResult:
    normalized_tasks: int = 0
    updated_sprints: int = 0
    updated_modules: int = 0
    updated_releases: int = 0
    overdue_notifications: int = 0
    activity_logs: int = 0

    def as_dict(self):
        return {
            "normalized_tasks": self.normalized_tasks,
            "updated_sprints": self.updated_sprints,
            "updated_modules": self.updated_modules,
            "updated_releases": self.updated_releases,
            "overdue_notifications": self.overdue_notifications,
            "activity_logs": self.activity_logs,
        }

    def get(self, key, default=None):
        return self.as_dict().get(key, default)


def _has_field(model_or_obj, field_name: str) -> bool:
    model = model_or_obj if hasattr(model_or_obj, "_meta") else model_or_obj.__class__
    return any(f.name == field_name for f in model._meta.fields)


def _save_fields(obj, fields):
    valid = [f for f in fields if _has_field(obj, f)]
    if valid:
        obj.save(update_fields=valid)


def _activity(title: str, description: str = "", task: Optional[Task] = None, user=None) -> int:
    data = {
        "action": "update",
        "title": title[:200],
        "description": description,
    }
    if _has_field(ActivityLog, "module") and task is not None:
        data["module"] = task.module
    if _has_field(ActivityLog, "task") and task is not None:
        data["task"] = task
    if _has_field(ActivityLog, "user") and user is not None and getattr(user, "is_authenticated", False):
        data["user"] = user
    ActivityLog.objects.create(**data)
    return 1


def _status_from_progress(progress: int, current_status: str = "todo") -> str:
    progress = max(0, min(int(progress or 0), 100))
    if progress >= 100:
        return "done"
    if progress <= 0:
        return "todo"
    if current_status == "review":
        return "review"
    return "doing"


def normalize_task(task: Task, user=None, create_log=True) -> int:
    old_status = task.status
    old_progress = int(task.progress or 0)

    task.progress = max(0, min(old_progress, 100))
    task.status = _status_from_progress(task.progress, task.status)

    if task.status != old_status or task.progress != old_progress:
        task.save(update_fields=["status", "progress"])
        if create_log:
            _activity(
                title=f"تحديث تلقائي للمهمة: {task.title}",
                description=f"الحالة: {old_status} → {task.status} | الإنجاز: {old_progress}% → {task.progress}%",
                task=task,
                user=user,
            )
        return 1
    return 0


def normalize_tasks(user=None) -> int:
    count = 0
    for task in Task.objects.select_related("module").all():
        count += normalize_task(task, user=user)
    return count


def _average_progress(tasks_qs) -> int:
    total = tasks_qs.count()
    if not total:
        return 0
    return round(sum(int(t.progress or 0) for t in tasks_qs) / total)


def recalc_sprints() -> int:
    updated = 0
    for sprint in Sprint.objects.prefetch_related("tasks").all():
        tasks = sprint.tasks.all()
        avg = _average_progress(tasks)
        old_status = sprint.status
        old_progress = getattr(sprint, "progress", None)

        if not tasks.exists():
            sprint.status = "planned"
        elif avg >= 100:
            sprint.status = "completed"
        elif avg > 0:
            sprint.status = "active"
        else:
            sprint.status = "planned"

        fields = ["status"]
        if _has_field(sprint, "progress"):
            sprint.progress = avg
            fields.append("progress")

        if sprint.status != old_status or (_has_field(sprint, "progress") and old_progress != avg):
            _save_fields(sprint, fields)
            updated += 1
    return updated


def recalc_modules() -> int:
    updated = 0
    if not _has_field(Module, "progress"):
        return 0
    for module in Module.objects.all():
        tasks = Task.objects.filter(module=module)
        avg = _average_progress(tasks)
        if module.progress != avg:
            module.progress = avg
            module.save(update_fields=["progress"])
            updated += 1
    return updated


def recalc_releases() -> int:
    updated = 0
    # حالياً نموذج Release لا يحتوي progress في أغلب النسخ، لكن ندعمه إذا أضيف لاحقاً.
    if not _has_field(Release, "progress"):
        return 0
    for release in Release.objects.all():
        tasks = Task.objects.filter(release=release)
        avg = _average_progress(tasks)
        if release.progress != avg:
            release.progress = avg
            release.save(update_fields=["progress"])
            updated += 1
    return updated


def generate_overdue_notifications() -> int:
    today = timezone.localdate()
    created = 0
    overdue_tasks = Task.objects.filter(due_date__lt=today).exclude(status="done")
    for task in overdue_tasks:
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


def run_workflow_engine(user=None) -> WorkflowResult:
    global _ENGINE_RUNNING
    if _ENGINE_RUNNING:
        return WorkflowResult()

    _ENGINE_RUNNING = True
    try:
        result = WorkflowResult()
        result.normalized_tasks = normalize_tasks(user=user)
        result.updated_sprints = recalc_sprints()
        result.updated_modules = recalc_modules()
        result.updated_releases = recalc_releases()
        result.overdue_notifications = generate_overdue_notifications()
        return result
    finally:
        _ENGINE_RUNNING = False


def sync_after_task_change(task=None, user=None):
    """تُستدعى من signals أو views بعد حفظ مهمة واحدة."""
    global _ENGINE_RUNNING
    if _ENGINE_RUNNING:
        return WorkflowResult()

    _ENGINE_RUNNING = True
    try:
        result = WorkflowResult()
        if task is not None:
            result.normalized_tasks = normalize_task(task, user=user)
        result.updated_sprints = recalc_sprints()
        result.updated_modules = recalc_modules()
        result.updated_releases = recalc_releases()
        result.overdue_notifications = generate_overdue_notifications()
        return result
    finally:
        _ENGINE_RUNNING = False


def update_task_status(task, status=None, progress=None, user=None):
    """تحديث آمن لحالة/نسبة المهمة من Kanban أو النماذج.

    يرجع tuple: (ok, message) حتى يتوافق مع views.task_update_status.
    """
    old_status = task.status
    old_progress = int(task.progress or 0)

    if status is not None:
        if status in ["doing", "review", "done"] and task.depends_on.exclude(status="done").exists():
            deps = "، ".join(task.depends_on.exclude(status="done").values_list("title", flat=True))
            return False, f"لا يمكن نقل هذه المهمة قبل إكمال: {deps}"
        task.status = status
        if status == "done":
            task.progress = 100
        elif status == "todo" and progress is None:
            task.progress = 0

    if progress is not None:
        try:
            task.progress = max(0, min(int(progress), 100))
        except (TypeError, ValueError):
            return False, "نسبة الإنجاز غير صالحة."
        task.status = _status_from_progress(task.progress, task.status)

    task.save(update_fields=["status", "progress"])
    _activity(
        title=f"تغيير حالة مهمة: {task.title}",
        description=f"{old_status} → {task.status} | {old_progress}% → {task.progress}%",
        task=task,
        user=user,
    )
    sync_after_task_change(task=task, user=user)
    return True, "تم تحديث المهمة بنجاح."
