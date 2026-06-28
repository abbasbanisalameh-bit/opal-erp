from django.contrib.auth.decorators import login_required
from django.forms import modelform_factory
from django.shortcuts import render, redirect, get_object_or_404

from .models import AcademicYear, Subject


AcademicYearForm = modelform_factory(
    AcademicYear,
    fields=["name", "start_date", "end_date", "is_active"]
)

SubjectForm = modelform_factory(
    Subject,
    fields=["name", "code", "grade", "is_active"]
)


@login_required
def academic_year_list(request):
    years = AcademicYear.objects.order_by("-start_date")
    return render(request, "academics/academic_year_list.html", {"years": years})


@login_required
def academic_year_create(request):
    form = AcademicYearForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("academics:academic_year_list")
    return render(request, "academics/academic_year_form.html", {"form": form, "title": "إضافة عام دراسي"})


@login_required
def academic_year_update(request, pk):
    year = get_object_or_404(AcademicYear, pk=pk)
    form = AcademicYearForm(request.POST or None, instance=year)
    if form.is_valid():
        form.save()
        return redirect("academics:academic_year_list")
    return render(request, "academics/academic_year_form.html", {"form": form, "title": "تعديل عام دراسي"})


@login_required
def subject_list(request):
    subjects = Subject.objects.select_related("grade").order_by("grade", "name")
    return render(request, "academics/subject_list.html", {"subjects": subjects})


@login_required
def subject_create(request):
    form = SubjectForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("academics:subject_list")
    return render(request, "academics/subject_form.html", {"form": form, "title": "إضافة مادة"})


@login_required
def subject_update(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    form = SubjectForm(request.POST or None, instance=subject)
    if form.is_valid():
        form.save()
        return redirect("academics:subject_list")
    return render(request, "academics/subject_form.html", {"form": form, "title": "تعديل مادة"})
