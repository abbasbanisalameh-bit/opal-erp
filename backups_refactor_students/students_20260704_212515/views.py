from django.shortcuts import render, get_object_or_404, redirect
from .models import Student
from .forms import StudentForm


def student_list(request):
    q = request.GET.get("q", "").strip()
    students = Student.objects.all().order_by("-id")

    if q:
        students = students.filter(full_name__icontains=q) | students.filter(student_number__icontains=q)

    return render(request, "students/student_list.html", {
        "students": students,
        "q": q,
    })


def student_detail(request, pk):
    student = get_object_or_404(Student, pk=pk)
    return render(request, "students/student_detail.html", {
        "student": student,
    })


def student_create(request):
    form = StudentForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        return redirect("students:student_list")
    return render(request, "students/student_form.html", {
        "form": form,
        "title": "إضافة طالب",
    })


def student_update(request, pk):
    student = get_object_or_404(Student, pk=pk)
    form = StudentForm(request.POST or None, request.FILES or None, instance=student)
    if form.is_valid():
        form.save()
        return redirect("students:student_detail", pk=student.pk)
    return render(request, "students/student_form.html", {
        "form": form,
        "title": "تعديل طالب",
    })


def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == "POST":
        student.status = "inactive"
        student.save(update_fields=["status"])
        return redirect("students:student_list")
    return render(request, "students/student_confirm_delete.html", {
        "student": student,
    })
