from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.utils import timezone

from academics.models import Enrollment, Grade
from .models import Attendance


@login_required
def attendance_dashboard(request):
    stats = Attendance.objects.values("status").annotate(total=Count("id"))

    return render(
        request,
        "attendance_v2/dashboard.html",
        {
            "stats": stats,
        },
    )


@login_required
def take_attendance(request):
    grade_id = request.GET.get("grade")
    date = request.GET.get("date") or timezone.localdate()

    students = []

    if grade_id:
        enrollments = (
            Enrollment.objects.filter(grade_id=grade_id)
            .select_related("student")
        )
        students = [e.student for e in enrollments]

    if request.method == "POST":
        date = request.POST.get("date")

        for key, value in request.POST.items():
            if key.startswith("status_"):
                student_id = key.replace("status_", "")

                Attendance.objects.update_or_create(
                    student_id=student_id,
                    date=date,
                    defaults={
                        "status": value,
                        "notes": request.POST.get(
                            f"notes_{student_id}",
                            ""
                        ),
                    },
                )

        return redirect("attendance_v2:dashboard")

    return render(
        request,
        "attendance_v2/take_attendance.html",
        {
            "grades": Grade.objects.all(),
            "students": students,
            "selected_grade": grade_id,
            "date": date,
        },
    )


@login_required
def attendance_report(request):
    records = Attendance.objects.select_related(
        "student"
    ).order_by("-date")

    grade = request.GET.get("grade")

    if grade:
        records = records.filter(
            student__enrollments__grade_id=grade
        )

    return render(
        request,
        "attendance_v2/report.html",
        {
            "records": records,
            "grades": Grade.objects.all(),
            "selected_grade": grade,
        },
    )