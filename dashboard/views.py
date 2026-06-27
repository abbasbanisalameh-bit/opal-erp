from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from academics.models import StudentRecord, Grade, Section
from admissions.models import AdmissionApplication


@login_required
def home(request):
    students_count = StudentRecord.objects.count()
    active_students = StudentRecord.objects.filter(is_active=True).count()
    grades_count = Grade.objects.count()
    sections_count = Section.objects.count()
    admissions_count = AdmissionApplication.objects.count()
    pending_admissions = AdmissionApplication.objects.exclude(status="converted").count()
    latest_students = StudentRecord.objects.all().order_by("-created_at")[:5]
    latest_admissions = AdmissionApplication.objects.all().order_by("-created_at")[:5]

    context = {
        "students_count": students_count,
        "active_students": active_students,
        "grades_count": grades_count,
        "sections_count": sections_count,
        "admissions_count": admissions_count,
        "pending_admissions": pending_admissions,
        "latest_students": latest_students,
        "latest_admissions": latest_admissions,
    }

    return render(request, "dashboard/home.html", context)
