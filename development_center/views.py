from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Module


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
        "current_version": "0.8 Alpha",
        "next_version": "1.0 Stable",
    }

    return render(request, "development_center/dashboard.html", context)

from .models import Task

@login_required
def tasks_board(request):
    context = {
        "todo": Task.objects.filter(status="todo"),
        "doing": Task.objects.filter(status="doing"),
        "review": Task.objects.filter(status="review"),
        "done": Task.objects.filter(status="done"),
    }
    return render(request, "development_center/tasks_board.html", context)
