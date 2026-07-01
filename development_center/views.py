from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import Module, Task, Release, Milestone, Idea, Decision, Bug, ActivityLog
from .forms import ModuleForm, TaskForm, ReleaseForm, MilestoneForm, IdeaForm, DecisionForm, BugForm


@login_required
def dashboard(request):
    modules = Module.objects.all()
    total = modules.count()

    tasks_total = Task.objects.count()
    tasks_done = Task.objects.filter(status="done").count()
    overall_progress = round((tasks_done / tasks_total) * 100) if tasks_total else 0

    return render(request, "development_center/dashboard.html", {
        "modules": modules.order_by("-progress"),
        "latest_tasks": Task.objects.select_related("module", "release").order_by("-id")[:8],
        "latest_bugs": Bug.objects.select_related("module").order_by("-id")[:8],
        "latest_releases": Release.objects.order_by("-id")[:5],
        "total": total,
        "completed": modules.filter(status="completed").count(),
        "development": modules.filter(status="development").count(),
        "planned": modules.filter(status="planned").count(),
        "progress": round(sum(m.progress for m in modules) / total) if total else 0,
        "overall_progress": overall_progress,
        "tasks_count": tasks_total,
        "tasks_done": tasks_done,
        "bugs_count": Bug.objects.count(),
        "ideas_count": Idea.objects.count(),
        "releases_count": Release.objects.count(),
    })

def crud_views(model, form_class, template_dir, url_name):
    @login_required
    def list_view(request):
        qs = model.objects.all()
        context = {"items": qs}
        if url_name == "module":
            context["modules"] = qs
        return render(request, f"development_center/{template_dir}/list.html", context)

    @login_required
    def create_view(request):
        form = form_class(request.POST or None)
        if form.is_valid():
            obj = form.save()
            ActivityLog.objects.create(
                action="create",
                title=f"إنشاء: {obj}",
                description=f"Model: {model.__name__}",
                user=request.user
            )
            return redirect(f"development_center:{url_name}_list")
        return render(request, "development_center/shared/form.html", {"form": form, "title": "إضافة"})

    @login_required
    def update_view(request, pk):
        obj = get_object_or_404(model, pk=pk)
        form = form_class(request.POST or None, instance=obj)
        if form.is_valid():
            obj = form.save()
            ActivityLog.objects.create(
                action="update",
                title=f"تعديل: {obj}",
                description=f"Model: {model.__name__}",
                user=request.user
            )
            return redirect(f"development_center:{url_name}_list")
        return render(request, "development_center/shared/form.html", {"form": form, "title": "تعديل"})

    @login_required
    def delete_view(request, pk):
        obj = get_object_or_404(model, pk=pk)
        ActivityLog.objects.create(
            action="delete",
            title=f"حذف: {obj}",
            description=f"Model: {model.__name__}",
            user=request.user
        )
        obj.delete()
        return redirect(f"development_center:{url_name}_list")

    return list_view, create_view, update_view, delete_view


module_list, module_create, module_update, module_delete = crud_views(Module, ModuleForm, "modules", "module")
release_list, release_create, release_update, release_delete = crud_views(Release, ReleaseForm, "releases", "release")
milestone_list, milestone_create, milestone_update, milestone_delete = crud_views(Milestone, MilestoneForm, "milestones", "milestone")
idea_list, idea_create, idea_update, idea_delete = crud_views(Idea, IdeaForm, "ideas", "idea")
decision_list, decision_create, decision_update, decision_delete = crud_views(Decision, DecisionForm, "decisions", "decision")
bug_list, bug_create, bug_update, bug_delete = crud_views(Bug, BugForm, "bugs", "bug")


@login_required
def task_list(request):
    tasks = Task.objects.select_related("module", "release").all()
    return render(request, "development_center/tasks/list.html", {"tasks": tasks})


@login_required
def task_detail(request, pk):
    task = get_object_or_404(Task.objects.select_related("module", "release"), pk=pk)
    logs = task.activity_logs.select_related("user", "module").all()[:20]
    return render(request, "development_center/tasks/detail.html", {"task": task, "logs": logs})


@login_required
def tasks_board(request):
    return render(request, "development_center/tasks_board.html", {
        "todo": Task.objects.select_related("module").filter(status="todo"),
        "doing": Task.objects.select_related("module").filter(status="doing"),
        "review": Task.objects.select_related("module").filter(status="review"),
        "done": Task.objects.select_related("module").filter(status="done"),
    })

from django.http import JsonResponse
from development_center.services.gantt_service import get_gantt_tasks, update_task_dates
from django.views.decorators.http import require_POST


@login_required
@require_POST
def task_update_status(request, pk):
    task = get_object_or_404(Task, pk=pk)
    new_status = request.POST.get("status")

    if new_status in ["todo", "doing", "review", "done"]:
        incomplete_dependencies = task.depends_on.exclude(status="done")

        if new_status in ["doing", "review", "done"] and incomplete_dependencies.exists():
            dependency_names = "، ".join(incomplete_dependencies.values_list("title", flat=True))
            return JsonResponse({
                "ok": False,
                "message": f"لا يمكن نقل هذه المهمة قبل إكمال: {dependency_names}"
            }, status=400)

        old_status = task.status
        task.status = new_status
        task.progress = 100 if new_status == "done" else task.progress
        task.save(update_fields=["status", "progress"])
        ActivityLog.objects.create(
            action="status",
            title=f"تغيير حالة مهمة: {task}",
            description=f"من {old_status} إلى {new_status}",
            module=task.module,
            task=task,
            user=request.user,
        )
        return JsonResponse({"ok": True})

    return JsonResponse({"ok": False}, status=400)


@login_required
def activity_list(request):
    logs = ActivityLog.objects.select_related("module", "task").all()[:100]
    return render(request, "development_center/activity/list.html", {"logs": logs})


@login_required
def task_create(request):
    form = TaskForm(request.POST or None)
    if form.is_valid():
        obj = form.save()
        ActivityLog.objects.create(
            action="create",
            title=f"إنشاء مهمة: {obj}",
            module=obj.module,
            task=obj,
            user=request.user,
        )
        return redirect("development_center:task_list")
    return render(request, "development_center/shared/form.html", {"form": form, "title": "إضافة مهمة"})


@login_required
def task_update(request, pk):
    obj = get_object_or_404(Task, pk=pk)
    form = TaskForm(request.POST or None, instance=obj)
    if form.is_valid():
        obj = form.save()
        ActivityLog.objects.create(
            action="update",
            title=f"تعديل مهمة: {obj}",
            module=obj.module,
            task=obj,
            user=request.user,
        )
        return redirect("development_center:task_list")
    return render(request, "development_center/shared/form.html", {"form": form, "title": "تعديل مهمة"})


@login_required
def task_delete(request, pk):
    obj = get_object_or_404(Task, pk=pk)
    ActivityLog.objects.create(
        action="delete",
        title=f"حذف مهمة: {obj}",
        module=obj.module,
        task=obj,
        user=request.user,
    )
    obj.delete()
    return redirect("development_center:task_list")

def gantt_chart(request):
    tasks = Task.objects.select_related("module", "release").all().order_by("start_date", "due_date", "id")

    dated_tasks = [t for t in tasks if t.start_date and t.due_date]

    if dated_tasks:
        min_date = min(t.start_date for t in dated_tasks)
        max_date = max(t.due_date for t in dated_tasks)
        total_days = max((max_date - min_date).days + 1, 1)
    else:
        min_date = None
        max_date = None
        total_days = 1

    rows = []
    for task in tasks:
        if task.start_date and task.due_date and min_date:
            offset = (task.start_date - min_date).days
            duration = max((task.due_date - task.start_date).days + 1, 1)
        else:
            offset = 0
            duration = 1

        rows.append({
            "task": task,
            "offset": offset,
            "duration": duration,
            "progress": task.progress or 0,
            "blocked": task.is_blocked,
            "has_dates": bool(task.start_date and task.due_date),
        })

    return render(request, "development_center/gantt.html", {
        "rows": rows,
        "min_date": min_date,
        "max_date": max_date,
        "total_days": total_days,
    })

def roadmap(request):
    releases = Release.objects.all().order_by("planned_date", "id")

    roadmap = []

    for release in releases:
        milestones = release.milestone_set.all().order_by("target_date")

        total = milestones.count()
        completed = milestones.filter(completed=True).count()

        progress = 0
        if total:
            progress = round(completed / total * 100)

        roadmap.append({
            "release": release,
            "milestones": milestones,
            "total": total,
            "completed": completed,
            "progress": progress,
        })

    return render(request, "development_center/roadmap.html", {
        "roadmap": roadmap,
    })

from django.http import JsonResponse

def gantt_data(request):
    return JsonResponse({"tasks": get_gantt_tasks()})


from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_date

@require_POST
def gantt_update_task_dates(request, pk):
    task = get_object_or_404(Task, pk=pk)

    ok, message = update_task_dates(
        task=task,
        start_date_value=request.POST.get("start_date", ""),
        due_date_value=request.POST.get("due_date", ""),
        user=request.user,
    )

    if not ok:
        return JsonResponse({"ok": False, "message": message}, status=400)

    return JsonResponse({"ok": True, "message": message})

from .models import Sprint, SprintDailySnapshot
from .forms import SprintForm

@login_required
def sprint_list(request):
    sprints = Sprint.objects.prefetch_related("tasks").all()
    return render(request, "development_center/sprints/list.html", {"sprints": sprints})

@login_required
def sprint_create(request):
    form = SprintForm(request.POST or None)
    if form.is_valid():
        sprint = form.save()
        ActivityLog.objects.create(
            action="create",
            title=f"إنشاء Sprint: {sprint}",
            description="تم إنشاء Sprint جديد",
            user=request.user,
        )
        return redirect("development_center:sprint_list")
    return render(request, "development_center/shared/form.html", {"form": form, "title": "إضافة Sprint"})

@login_required
def sprint_update(request, pk):
    sprint = get_object_or_404(Sprint, pk=pk)
    form = SprintForm(request.POST or None, instance=sprint)
    if form.is_valid():
        sprint = form.save()
        ActivityLog.objects.create(
            action="update",
            title=f"تعديل Sprint: {sprint}",
            description="تم تعديل Sprint",
            user=request.user,
        )
        return redirect("development_center:sprint_list")
    return render(request, "development_center/shared/form.html", {"form": form, "title": "تعديل Sprint"})

from django.utils import timezone

@login_required
def sprint_detail(request, pk):
    sprint = get_object_or_404(Sprint, pk=pk)
    tasks = sprint.tasks.all()

    total = tasks.count()
    done = tasks.filter(status="done").count()
    doing = tasks.filter(status="doing").count()
    review = tasks.filter(status="review").count()
    todo = tasks.filter(status="todo").count()
    remaining = total - done
    progress = round((done / total) * 100) if total else 0

    today = timezone.localdate()
    days_left = None
    if sprint.end_date:
        days_left = (sprint.end_date - today).days

    overdue_tasks = tasks.filter(due_date__lt=today).exclude(status="done")

    return render(request, "development_center/sprints/detail.html", {
        "sprint": sprint,
        "tasks": tasks,
        "total": total,
        "done": done,
        "doing": doing,
        "review": review,
        "todo": todo,
        "remaining": remaining,
        "progress": progress,
        "days_left": days_left,
        "overdue_tasks": overdue_tasks,
    })

@login_required
def sprint_board(request, pk):
    sprint = get_object_or_404(Sprint, pk=pk)

    tasks = sprint.tasks.all()

    context = {
        "sprint": sprint,
        "todo": tasks.filter(status="todo"),
        "doing": tasks.filter(status="doing"),
        "review": tasks.filter(status="review"),
        "done": tasks.filter(status="done"),
    }

    return render(request, "development_center/sprints/board.html", context)

@login_required
def product_backlog(request):
    tasks = Task.objects.filter(sprint__isnull=True).select_related("module", "release").order_by("-id")
    sprints = Sprint.objects.exclude(status="completed").order_by("-start_date", "-id")

    return render(request, "development_center/sprints/backlog.html", {
        "tasks": tasks,
        "sprints": sprints,
    })

import json
from datetime import timedelta

@login_required
def sprint_burndown(request, pk):
    sprint = get_object_or_404(Sprint, pk=pk)
    tasks = sprint.tasks.all()

    total = tasks.count()
    remaining = tasks.exclude(status="done").count()
    today = timezone.localdate()

    SprintDailySnapshot.objects.update_or_create(
        sprint=sprint,
        date=today,
        defaults={
            "total_tasks": total,
            "remaining_tasks": remaining,
        }
    )

    labels = []
    ideal = []
    actual = []

    if sprint.start_date and sprint.end_date:
        days_count = (sprint.end_date - sprint.start_date).days + 1
        days_count = max(days_count, 1)

        snapshots = {
            s.date: s.remaining_tasks
            for s in sprint.snapshots.all()
        }

        for i in range(days_count):
            day = sprint.start_date + timedelta(days=i)
            labels.append(day.strftime("%Y-%m-%d"))

            ideal_remaining = round(total - ((total / max(days_count - 1, 1)) * i))
            ideal.append(max(ideal_remaining, 0))

            actual.append(snapshots.get(day, None))
    else:
        labels = [today.strftime("%Y-%m-%d")]
        ideal = [total]
        actual = [remaining]

    return render(request, "development_center/sprints/burndown.html", {
        "sprint": sprint,
        "labels": json.dumps(labels),
        "ideal": json.dumps(ideal),
        "actual": json.dumps(actual),
        "total": total,
        "remaining": remaining,
    })

@login_required
def sprint_velocity(request):
    sprints = Sprint.objects.prefetch_related("tasks").all().order_by("start_date", "id")

    labels = []
    completed_tasks = []
    total_tasks = []

    for sprint in sprints:
        labels.append(sprint.title)
        total_tasks.append(sprint.tasks.count())
        completed_tasks.append(sprint.tasks.filter(status="done").count())

    avg_velocity = 0
    if completed_tasks:
        avg_velocity = round(sum(completed_tasks) / len(completed_tasks), 1)

    return render(request, "development_center/sprints/velocity.html", {
        "labels": json.dumps(labels),
        "completed_tasks": json.dumps(completed_tasks),
        "total_tasks": json.dumps(total_tasks),
        "avg_velocity": avg_velocity,
    })

from .models import Notification

@login_required
def notification_list(request):
    notifications = Notification.objects.all()
    return render(request, "development_center/notifications/list.html", {
        "notifications": notifications,
    })

@login_required
def notification_mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    return redirect("development_center:notification_list")

@login_required
def generate_task_notifications(request):
    today = timezone.localdate()
    overdue_tasks = Task.objects.filter(due_date__lt=today).exclude(status="done")

    created = 0

    for task in overdue_tasks:
        title = f"مهمة متأخرة: {task.title}"
        exists = Notification.objects.filter(title=title, is_read=False).exists()

        if not exists:
            Notification.objects.create(
                title=title,
                message=f"المهمة تجاوزت تاريخ النهاية المحدد: {task.due_date}",
                level="danger",
                url=f"/development/tasks/{task.id}/",
            )
            created += 1

    return redirect("development_center:notification_list")

@login_required
def executive_dashboard(request):
    modules_count = Module.objects.count()
    tasks = Task.objects.all()
    sprints = Sprint.objects.prefetch_related("tasks").all()
    releases = Release.objects.all()
    notifications = Notification.objects.all()[:8]

    total_tasks = tasks.count()
    done_tasks = tasks.filter(status="done").count()
    overdue_tasks = tasks.filter(due_date__lt=timezone.localdate()).exclude(status="done")
    open_bugs = Bug.objects.exclude(status="closed").count() if hasattr(Bug, "status") else Bug.objects.count()

    project_progress = round((done_tasks / total_tasks) * 100) if total_tasks else 0

    sprint_data = []
    for sprint in sprints[:6]:
        stotal = sprint.tasks.count()
        sdone = sprint.tasks.filter(status="done").count()
        sprogress = round((sdone / stotal) * 100) if stotal else 0
        sprint_data.append({
            "sprint": sprint,
            "total": stotal,
            "done": sdone,
            "progress": sprogress,
        })

    release_data = []
    for release in releases[:6]:
        r_tasks = release.tasks.all()
        r_total = r_tasks.count()
        r_done = r_tasks.filter(status="done").count()
        r_progress = round((r_done / r_total) * 100) if r_total else 0
        release_data.append({
            "release": release,
            "total": r_total,
            "done": r_done,
            "progress": r_progress,
        })

    return render(request, "development_center/executive_dashboard.html", {
        "modules_count": modules_count,
        "total_tasks": total_tasks,
        "done_tasks": done_tasks,
        "project_progress": project_progress,
        "overdue_tasks": overdue_tasks[:10],
        "open_bugs": open_bugs,
        "sprint_data": sprint_data,
        "release_data": release_data,
        "notifications": notifications,
    })

import csv
from django.http import HttpResponse

@login_required
def tasks_csv_report(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="development_tasks_report.csv"'
    response.write("\ufeff")

    writer = csv.writer(response)
    writer.writerow(["المهمة", "الوحدة", "الإصدار", "السبرنت", "الحالة", "الإنجاز", "البداية", "النهاية"])

    for task in Task.objects.select_related("module", "release", "sprint").all():
        writer.writerow([
            task.title,
            task.module or "",
            task.release or "",
            task.sprint or "",
            task.get_status_display(),
            f"{task.progress}%",
            task.start_date or "",
            task.due_date or "",
        ])

    return response


@login_required
def project_print_report(request):
    tasks = Task.objects.select_related("module", "release", "sprint").all()
    return render(request, "development_center/reports/project_print.html", {
        "tasks": tasks,
    })

@login_required
def executive_dashboard(request):
    today = timezone.localdate()

    tasks = Task.objects.select_related("module", "release", "sprint").all()
    sprints = Sprint.objects.prefetch_related("tasks").all().order_by("start_date", "id")
    releases = Release.objects.all()
    modules = Module.objects.all()

    total_tasks = tasks.count()
    done_tasks = tasks.filter(status="done").count()
    doing_tasks = tasks.filter(status="doing").count()
    review_tasks = tasks.filter(status="review").count()
    todo_tasks = tasks.filter(status="todo").count()
    remaining_tasks = total_tasks - done_tasks
    overdue_tasks = tasks.filter(due_date__lt=today).exclude(status="done")

    project_progress = round((done_tasks / total_tasks) * 100) if total_tasks else 0

    first_sprint = sprints.first()
    last_sprint = sprints.last()

    project_start = first_sprint.start_date if first_sprint else today
    project_end = last_sprint.end_date if last_sprint else today

    total_days = max((project_end - project_start).days + 1, 1)
    elapsed_days = max((today - project_start).days + 1, 0)
    remaining_days = max((project_end - today).days, 0)

    sprint_data = []
    for sprint in sprints:
        stasks = sprint.tasks.all()
        stotal = stasks.count()
        sdone = stasks.filter(status="done").count()
        sprint_data.append({
            "sprint": sprint,
            "total": stotal,
            "done": sdone,
            "progress": round((sdone / stotal) * 100) if stotal else 0,
        })

    module_data = []
    for module in modules:
        mtasks = tasks.filter(module=module)
        mtotal = mtasks.count()
        mdone = mtasks.filter(status="done").count()
        if mtotal:
            module_data.append({
                "module": module,
                "total": mtotal,
                "done": mdone,
                "progress": round((mdone / mtotal) * 100),
            })

    release_data = []
    for release in releases:
        rtasks = tasks.filter(release=release)
        rtotal = rtasks.count()
        rdone = rtasks.filter(status="done").count()
        release_data.append({
            "release": release,
            "total": rtotal,
            "done": rdone,
            "progress": round((rdone / rtotal) * 100) if rtotal else 0,
        })

    notifications = Notification.objects.all()[:8]

    return render(request, "development_center/executive_dashboard.html", {
        "total_tasks": total_tasks,
        "done_tasks": done_tasks,
        "doing_tasks": doing_tasks,
        "review_tasks": review_tasks,
        "todo_tasks": todo_tasks,
        "remaining_tasks": remaining_tasks,
        "overdue_tasks": overdue_tasks[:10],
        "overdue_count": overdue_tasks.count(),
        "project_progress": project_progress,
        "total_days": total_days,
        "elapsed_days": elapsed_days,
        "remaining_days": remaining_days,
        "project_start": project_start,
        "project_end": project_end,
        "sprint_data": sprint_data,
        "module_data": module_data,
        "release_data": release_data,
        "notifications": notifications,
    })
