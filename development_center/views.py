from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import Module, Task, Release, Milestone, Idea, Decision, Bug
from .forms import ModuleForm


@login_required
def dashboard(request):
    modules = Module.objects.all()
    context = {
        "modules": modules,
        "total": modules.count(),
        "completed": modules.filter(status="completed").count(),
        "development": modules.filter(status="development").count(),
        "planned": modules.filter(status="planned").count(),
        "progress": round(sum(m.progress for m in modules) / modules.count()) if modules.exists() else 0,
        "tasks_count": Task.objects.count(),
        "bugs_count": Bug.objects.count(),
        "ideas_count": Idea.objects.count(),
        "releases_count": Release.objects.count(),
    }
    return render(request, "development_center/dashboard.html", context)


@login_required
def module_list(request):
    modules = Module.objects.all()
    return render(request, "development_center/modules/list.html", {"modules": modules})


@login_required
def module_create(request):
    form = ModuleForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("development_center:module_list")
    return render(request, "development_center/modules/form.html", {"form": form, "title": "إضافة وحدة"})


@login_required
def module_update(request, pk):
    module = get_object_or_404(Module, pk=pk)
    form = ModuleForm(request.POST or None, instance=module)
    if form.is_valid():
        form.save()
        return redirect("development_center:module_list")
    return render(request, "development_center/modules/form.html", {"form": form, "title": "تعديل وحدة"})


@login_required
def module_delete(request, pk):
    module = get_object_or_404(Module, pk=pk)
    module.delete()
    return redirect("development_center:module_list")


@login_required
def tasks_board(request):
    context = {
        "todo": Task.objects.filter(status="todo"),
        "doing": Task.objects.filter(status="doing"),
        "review": Task.objects.filter(status="review"),
        "done": Task.objects.filter(status="done"),
    }
    return render(request, "development_center/tasks_board.html", context)

@login_required
def release_list(request):
    items = Release.objects.all()
    return render(request, "development_center/releases/list.html", {"items": items})


@login_required
def milestone_list(request):
    items = Milestone.objects.all()
    return render(request, "development_center/milestones/list.html", {"items": items})


@login_required
def idea_list(request):
    items = Idea.objects.all()
    return render(request, "development_center/ideas/list.html", {"items": items})


@login_required
def decision_list(request):
    items = Decision.objects.all()
    return render(request, "development_center/decisions/list.html", {"items": items})


@login_required
def bug_list(request):
    items = Bug.objects.all()
    return render(request, "development_center/bugs/list.html", {"items": items})
