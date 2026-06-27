from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from academics.models import StudentRecord
from exams.models import Exam
from accounting.models import StudentInvoice
from attendance_v2.models import Attendance
from announcements.models import Announcement

from django.db.models import Sum
from django.utils import timezone


@login_required
def home(request):

    today = timezone.localdate()

    students = StudentRecord.objects.count()

    exams = Exam.objects.count()

    invoices = StudentInvoice.objects.filter(
        paid=False
    )

    outstanding = (
        invoices.aggregate(
            total=Sum("amount")
        )["total"]
        or 0
    )

    absent_today = Attendance.objects.filter(
        date=today,
        status="absent"
    ).count()

    latest_announcements = (
        Announcement.objects
        .order_by("-id")[:5]
    )

    latest_exams = (
        Exam.objects
        .order_by("-id")[:5]
    )

    return render(
        request,
        "dashboard/index.html",
        {
            "students": students,
            "exams": exams,
            "outstanding": outstanding,
            "absent_today": absent_today,
            "latest_announcements": latest_announcements,
            "latest_exams": latest_exams,
        },
    )
