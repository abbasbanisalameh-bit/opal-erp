from django.contrib import messages
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from enterprise_ops.permissions import management_required
from enterprise_ops.services import audit
from .models import Curriculum
from .forms import CurriculumForm


@management_required
def curriculum_list(request):
    items = Curriculum.objects.select_related("academic_year", "grade", "subject").all()
    return render(request, "curriculum/curriculum_list.html", {"items": items})


@management_required
def curriculum_create(request):
    form = CurriculumForm(request.POST or None)
    if form.is_valid():
        item = form.save()
        audit(request, "create", "curriculum.Curriculum", item.pk, f"إضافة خطة دراسية: {item}")
        messages.success(request, "تمت إضافة بند الخطة الدراسية.")
        return redirect("curriculum:curriculum_list")
    return render(request, "curriculum/curriculum_form.html", {"form": form, "title": "إضافة خطة دراسية"})


@management_required
def curriculum_update(request, pk):
    item = get_object_or_404(Curriculum, pk=pk)
    if item.academic_year.is_closed:
        messages.error(request, "العام الدراسي مغلق ولا يمكن تعديل خطته التاريخية.")
        return redirect("curriculum:curriculum_list")
    form = CurriculumForm(request.POST or None, instance=item)
    if form.is_valid():
        item = form.save()
        audit(request, "update", "curriculum.Curriculum", item.pk, f"تعديل خطة دراسية: {item}")
        messages.success(request, "تم تحديث بند الخطة الدراسية.")
        return redirect("curriculum:curriculum_list")
    return render(request, "curriculum/curriculum_form.html", {"form": form, "title": "تعديل خطة دراسية"})


@management_required
@require_POST
def curriculum_delete(request, pk):
    item = get_object_or_404(Curriculum, pk=pk)
    if item.academic_year.is_closed:
        messages.error(request, "العام الدراسي مغلق ولا يمكن حذف خطته التاريخية.")
    else:
        description = str(item)
        item.delete()
        audit(request, "delete", "curriculum.Curriculum", pk, f"حذف خطة دراسية: {description}")
        messages.success(request, "تم حذف بند الخطة الدراسية.")
    return redirect("curriculum:curriculum_list")
