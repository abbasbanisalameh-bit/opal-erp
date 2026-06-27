from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone

from academics.models import StudentRecord
from exams.models import Exam
from accounting.models import StudentInvoice
from attendance_v2.models import Attendance
from announcements.models import Announcement


@login_required
def home(request):
    today = timezone.localdate()

    students = StudentRecord.objects.count()
    exams = Exam.objects.count()

    invoices = StudentInvoice.objects.filter(paid=False)

    outstanding = invoices.aggregate(
        total=Sum("amount")
    )["total"] or 0

    absent_today = Attendance.objects.filter(
        date=today,
        status="absent"
    ).count()

    latest_announcements = Announcement.objects.order_by("-id")[:5]

    latest_exams = Exam.objects.order_by("-id")[:5]

    monthly_income = (
        StudentInvoice.objects
        .filter(paid=True)
        .annotate(month=TruncMonth("due_date"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )

    return render(
        request,
        "dashboard/home.html",
        {
            "students": students,
            "exams": exams,
            "outstanding": outstanding,
            "absent_today": absent_today,
            "latest_announcements": latest_announcements,
            "latest_exams": latest_exams,
            "paid_invoices": StudentInvoice.objects.filter(paid=True).count(),
            "unpaid_invoices": StudentInvoice.objects.filter(paid=False).count(),
            "attendance_stats": Attendance.objects.values("status").annotate(total=Count("id")),
            "monthly_income": monthly_income,
        },
    )
