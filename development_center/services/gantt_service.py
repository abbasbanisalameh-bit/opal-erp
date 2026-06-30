from django.utils.dateparse import parse_date
from development_center.models import Task, ActivityLog


def get_gantt_tasks():
    tasks = Task.objects.select_related("module", "release").prefetch_related("depends_on").all()

    data = []
    for task in tasks:
        data.append({
            "id": task.id,
            "title": task.title,
            "module": str(task.module) if task.module else "",
            "release": str(task.release) if task.release else "",
            "status": task.status,
            "progress": task.progress,
            "start_date": task.start_date.isoformat() if task.start_date else "",
            "due_date": task.due_date.isoformat() if task.due_date else "",
            "blocked": task.is_blocked,
            "dependencies": list(task.depends_on.values_list("id", flat=True)),
        })

    return data


def update_task_dates(task, start_date_value, due_date_value, user=None):
    if task.is_blocked:
        return False, "لا يمكن تعديل مهمة محجوبة قبل اكتمال اعتمادياتها."

    start = parse_date(start_date_value or "")
    due = parse_date(due_date_value or "")

    if not start or not due:
        return False, "تواريخ غير صالحة."

    if due < start:
        return False, "تاريخ النهاية لا يمكن أن يكون قبل تاريخ البداية."

    old_start = task.start_date
    old_due = task.due_date

    task.start_date = start
    task.due_date = due
    task.save(update_fields=["start_date", "due_date"])

    ActivityLog.objects.create(
        action="update",
        title=f"تعديل تواريخ Gantt: {task}",
        description=f"من {old_start} - {old_due} إلى {start} - {due}",
        module=task.module,
        task=task,
        user=user if user and user.is_authenticated else None,
    )

    return True, "تم تحديث تواريخ المهمة بنجاح."
