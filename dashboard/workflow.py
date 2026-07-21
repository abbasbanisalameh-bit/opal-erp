"""Unified OPAL executive dashboard and reporting workflow.

This module centralizes the existing management snapshot, dashboard context,
and CSV export rows without changing calculations, permissions, templates, or
visible behavior.
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Max, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from academics.models import Section
from accounting.models import StudentInvoice, StudentPayment
from admissions.models import AdmissionApplication
from attendance_v2.models import Attendance
from documents.models import IssuedDocument
from enterprise_ops.services import feedback_satisfaction_snapshot
from exams.models import Exam, StudentMark
from students.models import Student
from teachers.models import Teacher
from timetable.models import TeacherAbsence


def is_management_user(user):
    return bool(user.is_authenticated and (user.is_staff or user.is_superuser))


def _money(value):
    return value or Decimal("0.00")


def build_executive_snapshot():
    today = timezone.localdate()
    period_start = today - timedelta(days=29)

    student_stats = Student.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
    )
    students_count = student_stats["total"]
    active_students = student_stats["active"]
    inactive_students = max(students_count - active_students, 0)

    teachers_count = Teacher.objects.filter(is_active=True).count()
    sections_count = Section.objects.count()
    exams_count = Exam.objects.count()

    today_attendance = Attendance.objects.filter(date=today).aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(status="present")),
        absent=Count("id", filter=Q(status="absent")),
        late=Count("id", filter=Q(status="late")),
        departed=Count("id", filter=Q(status="departed")),
    )
    present_today = today_attendance["present"]
    absent_today = today_attendance["absent"]
    late_today = today_attendance["late"]
    departed_today = today_attendance["departed"]
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
    paid_amount = _money(
        StudentPayment.objects.filter(status="posted").aggregate(total=Sum("amount"))["total"]
    )
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

    absent_students_today = list(
        Attendance.objects.filter(date=today, status="absent")
        .select_related("student", "grade", "section")
        .order_by("student__full_name")
    )
    absent_teachers_today = list(
        TeacherAbsence.objects.filter(date=today)
        .select_related("teacher")
        .order_by("teacher__full_name")
    )

    recent_payment_cutoff = today - timedelta(days=30)
    no_recent_payment_students = list(
        Student.objects.filter(is_active=True, invoices__status__in=["open", "partial"])
        .annotate(
            last_payment_date=Max(
                "invoices__payments__payment_date",
                filter=Q(invoices__payments__status="posted"),
            )
        )
        .filter(Q(last_payment_date__lt=recent_payment_cutoff) | Q(last_payment_date__isnull=True))
        .distinct()
        .order_by("full_name")[:40]
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
        "departed_today": departed_today,
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
        "absent_students_today": absent_students_today,
        "absent_teachers_today": absent_teachers_today,
        "no_recent_payment_students": no_recent_payment_students,
        "recent_payment_cutoff": recent_payment_cutoff,
    }


def build_dashboard_context():
    snapshot = build_executive_snapshot()
    snapshot.update({
        "students": snapshot["students_count"],
        "teachers": snapshot["teachers_count"],
        "sections": snapshot["sections_count"],
        "exams": snapshot["exams_count"],
        "total_income": snapshot["paid_amount"],
        "total_unpaid": snapshot["outstanding"],
        "latest_students": Student.objects.order_by("-created_at")[:8],
        "candidate_students": AdmissionApplication.objects.filter(status="candidate").count(),
    })
    return snapshot


def build_executive_export_rows(snapshot=None):
    snapshot = snapshot or build_executive_snapshot()
    return [
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


def build_attendance_detail_context():
    """Detailed attendance follow-up moved out of the compact dashboard."""
    snapshot = build_executive_snapshot()
    return {
        "today": snapshot["today"],
        "period_start": snapshot["period_start"],
        "present_today": snapshot["present_today"],
        "absent_today": snapshot["absent_today"],
        "late_today": snapshot["late_today"],
        "departed_today": snapshot["departed_today"],
        "attendance_percent": snapshot["attendance_percent"],
        "attendance_trend": snapshot["attendance_trend"],
        "attendance_watch": snapshot["attendance_watch"],
        "absent_students_today": snapshot["absent_students_today"],
        "absent_teachers_today": snapshot["absent_teachers_today"],
    }
