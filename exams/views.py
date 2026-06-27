from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from .models import Exam, StudentMark
from academics.models import Enrollment
from .forms import ExamForm, StudentMarkForm


@login_required
def exam_list(request):
    exams = Exam.objects.all()
    return render(request, "exams/exam_list.html", {"exams": exams})


@login_required
def exam_create(request):
    form = ExamForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("exams:exam_list")
    return render(request, "exams/exam_form.html", {"form": form, "title": "إضافة امتحان"})


@login_required
def mark_create(request):
    form = StudentMarkForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("exams:mark_list")
    return render(request, "exams/mark_form.html", {"form": form, "title": "إدخال علامة"})


@login_required
def mark_list(request):
    marks = StudentMark.objects.select_related("student", "exam").all()
    return render(request, "exams/mark_list.html", {"marks": marks})


@login_required
def exam_marks_bulk(request, exam_id):
    exam = get_object_or_404(Exam, pk=exam_id)

    enrollments = Enrollment.objects.filter(
        grade=exam.grade,
        academic_year=exam.academic_year
    ).select_related("student")

    students = [e.student for e in enrollments]
    existing = {
        m.student_id: m.mark
        for m in StudentMark.objects.filter(exam=exam)
    }

    if request.method == "POST":
        for student in students:
            value = request.POST.get(f"mark_{student.id}")
            if value not in [None, ""]:
                StudentMark.objects.update_or_create(
                    exam=exam,
                    student=student,
                    defaults={"mark": value}
                )
        return redirect("exams:mark_list")

    return render(request, "exams/bulk_marks.html", {
        "exam": exam,
        "students": students,
        "existing": existing,
    })


@login_required
def exam_detail(request, exam_id):
    exam = get_object_or_404(Exam, pk=exam_id)
    marks = StudentMark.objects.filter(exam=exam).select_related("student").order_by("-mark")

    total = marks.count()
    values = [float(m.mark) for m in marks]

    stats = {
        "count": total,
        "highest": max(values) if values else 0,
        "lowest": min(values) if values else 0,
        "average": round(sum(values) / total, 2) if total else 0,
        "passed": sum(1 for m in marks if m.percentage >= 60),
        "failed": sum(1 for m in marks if m.percentage < 60),
    }

    return render(request, "exams/exam_detail.html", {
        "exam": exam,
        "marks": marks,
        "stats": stats,
    })


@login_required
def exam_update(request, exam_id):
    exam = get_object_or_404(Exam, pk=exam_id)
    form = ExamForm(request.POST or None, instance=exam)
    if form.is_valid():
        form.save()
        return redirect("exams:exam_detail", exam_id=exam.id)
    return render(request, "exams/exam_form.html", {"form": form, "title": "تعديل امتحان"})


@login_required
def exam_delete(request, exam_id):
    exam = get_object_or_404(Exam, pk=exam_id)
    if request.method == "POST":
        exam.delete()
        return redirect("exams:exam_list")
    return render(request, "exams/exam_confirm_delete.html", {"exam": exam})
