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

from .models import Sprint
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
