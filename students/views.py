from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import Student
from .forms import StudentForm

@login_required
def student_list(request):
    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()

    students = Student.objects.all().order_by("full_name")

    if q:
        students = students.filter(full_name__icontains=q) | Student.objects.filter(student_number__icontains=q)

    if status_filter:
        students = students.filter(status=status_filter)

    return render(request, "students/student_list.html", {
        "students": students,
        "q": q,
        "status_filter": status_filter,
        "status_choices": Student.STATUS_CHOICES,
    })

@login_required
def student_detail(request, pk):
    student = get_object_or_404(Student, pk=pk)
    return render(request, "students/student_detail.html", {"student": student})

@login_required
def student_create(request):
    if request.method == "POST":
        form = StudentForm(request.POST, request.FILES)
        if form.is_valid():
            student = form.save()
            return redirect("students:student_detail", pk=student.pk)
    else:
        form = StudentForm()
    return render(request, "students/student_form.html", {"form": form, "title": "إضافة طالب"})

@login_required
def student_update(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == "POST":
        form = StudentForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            form.save()
            return redirect("students:student_detail", pk=student.pk)
    else:
        form = StudentForm(instance=student)
    return render(request, "students/student_form.html", {"form": form, "title": "تعديل طالب"})

@login_required
def student_archive(request, pk):
    student = get_object_or_404(Student, pk=pk)
    student.status = "archived"
    student.save(update_fields=["status"])
    return redirect("students:student_list")
