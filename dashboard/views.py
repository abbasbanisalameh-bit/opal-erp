import csv
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from academics.models import Section
from accounting.models import StudentInvoice, StudentPayment
from announcements.models import Announcement
from attendance_v2.models import Attendance
from documents.models import IssuedDocument
from admissions.models import AdmissionApplication
from exams.models import Exam, StudentMark
from enterprise_ops.services import feedback_satisfaction_snapshot
from students.models import Student


def _is_management_user(user):
    return bool(user.is_authenticated and (user.is_staff or user.is_superuser))


def _money(value):
    return value or Decimal("0.00")


def _executive_snapshot():
    today = timezone.localdate()
    period_start = today - timedelta(days=29)

    student_stats = Student.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
    )
    students_count = student_stats["total"]
    active_students = student_stats["active"]
    inactive_students = max(students_count - active_students, 0)

    teachers_count = User.objects.filter(is_staff=True, is_active=True).count()
    sections_count = Section.objects.count()
    exams_count = Exam.objects.count()

    today_attendance = Attendance.objects.filter(date=today).aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(status="present")),
        absent=Count("id", filter=Q(status="absent")),
        late=Count("id", filter=Q(status="late")),
        excused=Count("id", filter=Q(status="excused")),
    )
    present_today = today_attendance["present"]
    absent_today = today_attendance["absent"]
    late_today = today_attendance["late"]
    excused_today = today_attendance["excused"]
    attendance_total_today = today_attendance["total"]
    attendance_percent = (
        round((present_today / attendance_total_today) * 100)
        if attendance_total_today
        else 0
    )

    period_attendance = Attendance.objects.filter(
        date__gte=period_start,
        date__lte=today,
    ).aggregate(
        absent=Count("id", filter=Q(status="absent")),
        late=Count("id", filter=Q(status="late")),
    )
    period_absences = period_attendance["absent"]
    period_late = period_attendance["late"]

    net_invoice_amount = ExpressionWrapper(
        F("amount") - F("discount_amount"),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    invoice_stats = StudentInvoice.objects.aggregate(
        total=Coalesce(
            Sum(net_invoice_amount, filter=~Q(status="cancelled")),
            Decimal("0.00"),
        ),
        paid_count=Count("id", filter=Q(status="paid")),
        unpaid_count=Count("id", filter=~Q(status__in=["paid", "cancelled"])),
        overdue_count=Count(
            "id",
            filter=Q(due_date__lt=today) & ~Q(status__in=["paid", "cancelled"]),
        ),
    )
    total_invoices = invoice_stats["total"]
    paid_amount = _money(StudentPayment.objects.filter(status="posted").aggregate(total=Sum("amount"))["total"])
    outstanding = max(total_invoices - paid_amount, Decimal("0.00"))
    collection_rate = (
        round((paid_amount / total_invoices) * 100, 1)
        if total_invoices > 0
        else 0
    )
    overdue_invoices = invoice_stats["overdue_count"]

    passing_mark = ExpressionWrapper(
        F("exam__max_mark") * F("exam__pass_percentage") / Value(100),
        output_field=DecimalField(max_digits=10, decimal_places=4),
    )
    mark_stats = StudentMark.objects.annotate(passing_mark=passing_mark).aggregate(
        average=Avg("mark"),
        total=Count("id"),
        passed=Count("id", filter=Q(mark__gte=F("passing_mark"))),
    )
    academic_average = mark_stats["average"] or Decimal("0.00")
    marks_count = mark_stats["total"]
    passed_marks = mark_stats["passed"]
    pass_rate = round((passed_marks / marks_count) * 100, 1) if marks_count else 0

    monthly_income = (
        StudentPayment.objects.filter(status="posted")
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

    trend_start = today - timedelta(days=6)
    attendance_by_day = {
        row["date"]: row
        for row in (
            Attendance.objects.filter(date__gte=trend_start, date__lte=today)
            .values("date")
            .annotate(
                total=Count("id"),
                present=Count("id", filter=Q(status="present")),
            )
        )
    }
    attendance_trend = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        daily = attendance_by_day.get(day, {})
        total = daily.get("total", 0)
        present = daily.get("present", 0)
        attendance_trend.append({
            "date": day.strftime("%m-%d"),
            "percent": round((present / total) * 100) if total else 0,
        })

    # A lightweight management watchlist: financial exposure + attendance risk.
    financial_watch = list(
        StudentInvoice.objects
        .exclude(status__in=["paid", "cancelled"])
        .values("student_id", "student__full_name", "student__student_number")
        .annotate(total_due=Sum(F("amount") - F("discount_amount")))
        .order_by("-total_due")[:8]
    )
    attendance_watch = list(
        Attendance.objects
        .filter(date__gte=period_start, status__in=["absent", "late"])
        .values("student_id", "student__full_name", "student__student_number")
        .annotate(risk_events=Count("id"))
        .order_by("-risk_events")[:8]
    )

    satisfaction = feedback_satisfaction_snapshot(today=today)

    return {
        **satisfaction,
        "today": today,
        "period_start": period_start,
        "students_count": students_count,
        "active_students": active_students,
        "inactive_students": inactive_students,
        "teachers_count": teachers_count,
        "sections_count": sections_count,
        "exams_count": exams_count,
        "present_today": present_today,
        "absent_today": absent_today,
        "late_today": late_today,
        "excused_today": excused_today,
        "attendance_percent": attendance_percent,
        "period_absences": period_absences,
        "period_late": period_late,
        "paid_amount": paid_amount,
        "total_invoices": total_invoices,
        "outstanding": outstanding,
        "collection_rate": collection_rate,
        "overdue_invoices": overdue_invoices,
        "paid_invoices": invoice_stats["paid_count"],
        "unpaid_invoices": invoice_stats["unpaid_count"],
        "academic_average": academic_average,
        "pass_rate": pass_rate,
        "marks_count": marks_count,
        "issued_documents": IssuedDocument.objects.count(),
        "monthly_income_labels": monthly_income_labels,
        "monthly_income_values": monthly_income_values,
        "attendance_trend": attendance_trend,
        "financial_watch": financial_watch,
        "attendance_watch": attendance_watch,
    }


@login_required
@user_passes_test(_is_management_user)
def home(request):
    snapshot = _executive_snapshot()
    snapshot.update({
        "students": snapshot["students_count"],
        "teachers": snapshot["teachers_count"],
        "sections": snapshot["sections_count"],
        "exams": snapshot["exams_count"],
        "total_income": snapshot["paid_amount"],
        "total_unpaid": snapshot["outstanding"],
        "latest_students": Student.objects.order_by("-created_at")[:8],
        "latest_announcements": Announcement.objects.order_by("-id")[:5],
        "latest_exams": Exam.objects.order_by("-id")[:5],
        "candidate_students": AdmissionApplication.objects.filter(status="candidate").count(),
    })
    return render(request, "dashboard/home.html", snapshot)


@login_required
@user_passes_test(_is_management_user)
def executive_export_csv(request):
    snapshot = _executive_snapshot()
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="opal_executive_snapshot.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["المؤشر", "القيمة"])
    rows = [
        ("تاريخ التقرير", snapshot["today"]),
        ("إجمالي الطلاب", snapshot["students_count"]),
        ("الطلاب النشطون", snapshot["active_students"]),
        ("المعلمون النشطون", snapshot["teachers_count"]),
        ("الشعب", snapshot["sections_count"]),
        ("نسبة الحضور اليوم", f'{snapshot["attendance_percent"]}%'),
        ("غيابات آخر 30 يومًا", snapshot["period_absences"]),
        ("تأخر آخر 30 يومًا", snapshot["period_late"]),
        ("إجمالي الفواتير", snapshot["total_invoices"]),
        ("إجمالي التحصيل", snapshot["paid_amount"]),
        ("إجمالي المستحق", snapshot["outstanding"]),
        ("نسبة التحصيل", f'{snapshot["collection_rate"]}%'),
        ("الفواتير المتأخرة", snapshot["overdue_invoices"]),
        ("متوسط العلامات", snapshot["academic_average"]),
        ("نسبة النجاح", f'{snapshot["pass_rate"]}%'),
        ("الوثائق المصدرة", snapshot["issued_documents"]),
    ]
    writer.writerows(rows)
    return response
