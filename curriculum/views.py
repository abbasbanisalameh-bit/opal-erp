from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import Curriculum
from .forms import CurriculumForm


@login_required
def curriculum_list(request):
    items = Curriculum.objects.select_related("academic_year", "grade", "subject").all()
    return render(request, "curriculum/curriculum_list.html", {"items": items})


@login_required
def curriculum_create(request):
    form = CurriculumForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("curriculum:curriculum_list")
    return render(request, "curriculum/curriculum_form.html", {"form": form, "title": "إضافة خطة دراسية"})


@login_required
def curriculum_update(request, pk):
    item = get_object_or_404(Curriculum, pk=pk)
    form = CurriculumForm(request.POST or None, instance=item)
    if form.is_valid():
        form.save()
        return redirect("curriculum:curriculum_list")
    return render(request, "curriculum/curriculum_form.html", {"form": form, "title": "تعديل خطة دراسية"})


@login_required
def curriculum_delete(request, pk):
    item = get_object_or_404(Curriculum, pk=pk)
    item.delete()
    return redirect("curriculum:curriculum_list")
