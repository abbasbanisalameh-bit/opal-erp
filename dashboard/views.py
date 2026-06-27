from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils import timezone

from academics.models import Section, StudentRecord
from accounting.models import StudentInvoice, StudentPayment
from announcements.models import Announcement
from attendance_v2.models import Attendance
from exams.models import Exam


@login_required
def home(request):
    today = timezone.localdate()

    students_count = StudentRecord.objects.count()
    teachers_count = User.objects.filter(is_staff=True).count()
    sections_count = Section.objects.count()
    exams_count = Exam.objects.count()

    present_today = Attendance.objects.filter(date=today, status="present").count()
    absent_today = Attendance.objects.filter(date=today, status="absent").count()
    total_attendance_today = present_today + absent_today
    attendance_percent = 0
    if total_attendance_today:
        attendance_percent = round((present_today / total_attendance_today) * 100)

    paid_amount = (
        StudentPayment.objects.aggregate(total=Sum("amount"))["total"]
        or 0
    )

    total_invoices = (
        StudentInvoice.objects.aggregate(total=Sum("amount"))["total"]
        or 0
    )

    outstanding = total_invoices - paid_amount

    monthly_income = (
        StudentPayment.objects
        .annotate(month=TruncMonth("payment_date"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )

    monthly_income_labels = []
    monthly_income_values = []
    for row in monthly_income:
        month = row.get("month")
        monthly_income_labels.append(month.strftime("%Y-%m") if month else "-")
        monthly_income_values.append(float(row.get("total") or 0))

    latest_students = StudentRecord.objects.order_by("-created_at")[:8]
    latest_announcements = Announcement.objects.order_by("-id")[:5]
    latest_exams = Exam.objects.order_by("-id")[:5]

    latest_activities = [
        f"عدد الطلاب الحالي: {students_count}",
        f"حضور اليوم: {present_today}",
        f"غياب اليوم: {absent_today}",
        f"إجمالي المدفوعات: {paid_amount}",
    ]

    return render(
        request,
        "dashboard/home.html",
        {
            "students": students_count,
            "teachers": teachers_count,
            "sections": sections_count,
            "exams": exams_count,
            "present_today": present_today,
            "absent_today": absent_today,
            "attendance_percent": attendance_percent,
            "paid_amount": paid_amount,
            "outstanding": outstanding,
            "total_income": paid_amount,
            "total_unpaid": outstanding,
            "paid_invoices": StudentInvoice.objects.filter(paid=True).count(),
            "unpaid_invoices": StudentInvoice.objects.filter(paid=False).count(),
            "latest_students": latest_students,
            "latest_announcements": latest_announcements,
            "latest_exams": latest_exams,
            "latest_activities": latest_activities,
            "monthly_income": monthly_income,
            "monthly_income_labels": monthly_income_labels,
            "monthly_income_values": monthly_income_values,
            "attendance_stats": Attendance.objects.values("status").annotate(total=Count("id")),
        },
    )
