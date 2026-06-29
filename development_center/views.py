from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import Module, Task, Release, Milestone, Idea, Decision, Bug
from .forms import ModuleForm, ReleaseForm, MilestoneForm, IdeaForm, DecisionForm, BugForm


@login_required
def dashboard(request):
    modules = Module.objects.all()
    total = modules.count()
    return render(request, "development_center/dashboard.html", {
        "modules": modules.order_by("-progress"),
        "latest_tasks": Task.objects.select_related("module").order_by("-id")[:8],
        "latest_bugs": Bug.objects.select_related("module").order_by("-id")[:8],
        "latest_releases": Release.objects.order_by("-id")[:5],
        "total": total,
        "completed": modules.filter(status="completed").count(),
        "development": modules.filter(status="development").count(),
        "planned": modules.filter(status="planned").count(),
        "progress": round(sum(m.progress for m in modules) / total) if total else 0,
        "tasks_count": Task.objects.count(),
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
            form.save()
            return redirect(f"development_center:{url_name}_list")
        return render(request, "development_center/shared/form.html", {"form": form, "title": "إضافة"})

    @login_required
    def update_view(request, pk):
        obj = get_object_or_404(model, pk=pk)
        form = form_class(request.POST or None, instance=obj)
        if form.is_valid():
            form.save()
            return redirect(f"development_center:{url_name}_list")
        return render(request, "development_center/shared/form.html", {"form": form, "title": "تعديل"})

    @login_required
    def delete_view(request, pk):
        obj = get_object_or_404(model, pk=pk)
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
def tasks_board(request):
    return render(request, "development_center/tasks_board.html", {
        "todo": Task.objects.filter(status="todo"),
        "doing": Task.objects.filter(status="doing"),
        "review": Task.objects.filter(status="review"),
        "done": Task.objects.filter(status="done"),
    })

from django.http import JsonResponse
from django.views.decorators.http import require_POST


@login_required
@require_POST
def task_update_status(request, pk):
    task = get_object_or_404(Task, pk=pk)
    new_status = request.POST.get("status")

    if new_status in ["todo", "doing", "review", "done"]:
        task.status = new_status
        task.save(update_fields=["status"])
        return JsonResponse({"ok": True})

    return JsonResponse({"ok": False}, status=400)
