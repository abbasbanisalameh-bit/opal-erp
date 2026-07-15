from django.shortcuts import render, redirect, get_object_or_404
from enterprise_ops.permissions import management_required
from .models import Student
from .forms import StudentForm
from .student360 import build_student_360_context

@management_required
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

@management_required
def student_detail(request, pk):
    # رابط متوافق مع الصفحات القديمة؛ ملف الطالب الموحد هو Student 360°.
    get_object_or_404(Student, pk=pk)
    return redirect("students:student_360", pk=pk)

@management_required
def student_create(request):
    # تم اعتماد نموذج التسجيل الذكي كنموذج التسجيل الوحيد في النظام.
    return redirect("/admissions/register/")

@management_required
def student_update(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == "POST":
        form = StudentForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            form.save()
            return redirect("students:student_360", pk=student.pk)
    else:
        form = StudentForm(instance=student)
    return render(request, "students/student_form.html", {"form": form, "title": "تعديل طالب"})

@management_required
def student_archive(request, pk):
    student = get_object_or_404(Student, pk=pk)
    # Status changes must pass through the audited academic lifecycle service.
    return redirect("academics:lifecycle_action", student_id=student.pk)


@management_required
def student_360(request, pk):
    student = get_object_or_404(Student, pk=pk)
    return render(request, "students/student_360.html", build_student_360_context(student))


@management_required
def student_360_print(request, pk):
    student = get_object_or_404(Student, pk=pk)
    return render(request, "students/student_360_print.html", build_student_360_context(student))
