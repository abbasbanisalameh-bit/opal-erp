"""Canonical OPAL executive dashboard data workflow.

Update 131.7 R2 makes every visible dashboard value traceable to persisted
records in the active school and current academic year.  Missing source data is
reported as unavailable; it is never converted into a fabricated zero result.
"""

from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Max, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from academics.models import Enrollment, Grade, Section
from accounting.models import StudentInvoice, StudentPayment
from announcements.models import Announcement
from attendance_v2.analytics import build_school_attendance_period_snapshot
from attendance_v2.models import Attendance
from core.models import AcademicYear
from documents.models import IssuedDocument
from enterprise_ops.models import BroadcastMessage, FeedbackTicket
from enterprise_ops.services import feedback_satisfaction_snapshot
from exams.models import Exam, StudentMark
from parent_portal.evaluation_services import monthly_teacher_evaluation_snapshot
from students.models import Student
from teachers.models import Teacher
from timetable.models import TeacherAbsence


MONEY_FIELD = DecimalField(max_digits=14, decimal_places=2)
ZERO_MONEY = Value(Decimal("0.00"), output_field=MONEY_FIELD)
OFFICIAL_EXAM_STATUSES = ("approved", "published", "closed")


def is_management_user(user):
    """Use OPAL's shared management rule for the executive gateway."""
    from accounts.workflow import is_management_user as canonical_management_user

    return canonical_management_user(user)


def _money(value):
    return value or Decimal("0.00")


def _resolve_scope(*, request=None, school=None, academic_year=None):
    """Resolve one school/year scope without creating or mutating records."""
    if school is None:
        if request is not None:
            from core.request_scope import request_school

            school = request_school(request)
        else:
            from admissions.services import active_school

            school = active_school()
    if academic_year is None and school is not None:
        academic_year = (
            AcademicYear.objects.filter(school=school, is_current=True)
            .order_by("-start_date", "-pk")
            .first()
        )
    return school, academic_year


def _empty_attendance_period(start_date, end_date):
    days = {}
    cursor = start_date
    while cursor <= end_date:
        days[cursor] = {
            "date": cursor,
            "roster_total": 0,
            "present": 0,
            "absent": 0,
            "departed": 0,
            "exceptions": 0,
            "percent": 0,
            "submitted_sections": 0,
            "closed_sections": 0,
            "pending_sections": 0,
            "has_data": False,
            "unregistered_absent": 0,
            "unregistered_departed": 0,
            "unregistered_exceptions": 0,
            "absent_student_ids": [],
            "departed_student_ids": [],
        }
        cursor += timedelta(days=1)
    totals = {
        "roster_total": 0,
        "present": 0,
        "absent": 0,
        "departed": 0,
        "exceptions": 0,
        "percent": 0,
        "submitted_sections": 0,
        "closed_sections": 0,
        "pending_sections": 0,
        "has_data": False,
        "unregistered_absent": 0,
        "unregistered_departed": 0,
        "unregistered_exceptions": 0,
    }
    return {"start_date": start_date, "end_date": end_date, "days": days, "totals": totals}


def _financial_snapshot(*, today, academic_year):
    """Return exact current-year invoice/payment values and the 30-day watch."""
    empty = {
        "finance_data_available": False,
        "total_invoices": Decimal("0.00"),
        "paid_amount": Decimal("0.00"),
        "outstanding": Decimal("0.00"),
        "collection_rate": 0,
        "overdue_invoices": 0,
        "paid_invoices": 0,
        "unpaid_invoices": 0,
        "monthly_income_labels": [],
        "monthly_income_values": [],
        "no_recent_payment_students": [],
        "no_recent_payment_total": 0,
        "recent_payment_cutoff": today - timedelta(days=30),
    }
    if academic_year is None:
        return empty

    invoice_qs = StudentInvoice.objects.filter(academic_year=academic_year).exclude(status="cancelled")
    invoice_rows = list(
        invoice_qs.annotate(
            posted_total=Coalesce(
                Sum("payments__amount", filter=Q(payments__status="posted")),
                ZERO_MONEY,
                output_field=MONEY_FIELD,
            )
        ).values(
            "id",
            "student_id",
            "amount",
            "discount_amount",
            "due_date",
            "issue_date",
            "posted_total",
        )
    )

    total_invoices = Decimal("0.00")
    paid_amount = Decimal("0.00")
    outstanding = Decimal("0.00")
    overdue_invoices = 0
    paid_invoices = 0
    unpaid_invoices = 0
    overdue_30_by_student = defaultdict(lambda: Decimal("0.00"))
    cutoff = today - timedelta(days=30)

    for row in invoice_rows:
        net = max(_money(row["amount"]) - _money(row["discount_amount"]), Decimal("0.00"))
        paid = max(_money(row["posted_total"]), Decimal("0.00"))
        remaining = max(net - paid, Decimal("0.00"))
        total_invoices += net
        paid_amount += paid
        outstanding += remaining
        if remaining <= 0:
            paid_invoices += 1
        else:
            unpaid_invoices += 1
            if row["due_date"] < today:
                overdue_invoices += 1
            if row["due_date"] <= cutoff:
                overdue_30_by_student[row["student_id"]] += remaining

    applied_paid = min(paid_amount, total_invoices)
    collection_rate = round((applied_paid / total_invoices) * 100, 1) if total_invoices > 0 else 0

    payment_qs = StudentPayment.objects.filter(
        status="posted",
        invoice__academic_year=academic_year,
    ).exclude(invoice__status="cancelled")
    monthly_income = list(
        payment_qs.annotate(month=TruncMonth("payment_date"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )
    monthly_income_labels = [row["month"].strftime("%Y-%m") for row in monthly_income if row.get("month")]
    monthly_income_values = [float(row.get("total") or 0) for row in monthly_income if row.get("month")]

    no_recent_payment_students = []
    watched_ids = list(overdue_30_by_student)
    if watched_ids:
        last_payments = {
            row["invoice__student_id"]: row["last_payment_date"]
            for row in payment_qs.filter(invoice__student_id__in=watched_ids)
            .values("invoice__student_id")
            .annotate(last_payment_date=Max("payment_date"))
        }
        eligible_ids = [
            student_id
            for student_id in watched_ids
            if last_payments.get(student_id) is None or last_payments[student_id] < cutoff
        ]
        enrollment_rows = Enrollment.objects.filter(
            academic_year=academic_year,
            status="active",
            student__is_active=True,
            student_id__in=eligible_ids,
        ).select_related("student", "grade", "section")
        for enrollment in enrollment_rows:
            no_recent_payment_students.append({
                "student": enrollment.student,
                "grade": enrollment.grade,
                "section": enrollment.section,
                "last_payment_date": last_payments.get(enrollment.student_id),
                "outstanding": overdue_30_by_student[enrollment.student_id],
            })
        no_recent_payment_students.sort(
            key=lambda row: (
                row["last_payment_date"] is not None,
                row["last_payment_date"] or date.min,
                -row["outstanding"],
                row["student"].full_name,
            )
        )

    return {
        "finance_data_available": bool(invoice_rows),
        "total_invoices": total_invoices,
        "paid_amount": paid_amount,
        "outstanding": outstanding,
        "collection_rate": collection_rate,
        "overdue_invoices": overdue_invoices,
        "paid_invoices": paid_invoices,
        "unpaid_invoices": unpaid_invoices,
        "monthly_income_labels": monthly_income_labels,
        "monthly_income_values": monthly_income_values,
        "no_recent_payment_students": no_recent_payment_students[:40],
        "no_recent_payment_total": len(no_recent_payment_students),
        "recent_payment_cutoff": cutoff,
    }


def build_executive_snapshot(
    *,
    request=None,
    school=None,
    academic_year=None,
    include_secondary_metrics=True,
    include_financial_watch=True,
    include_attendance_watch=True,
):
    """Build the authoritative manager snapshot for one school and current year."""
    school, academic_year = _resolve_scope(request=request, school=school, academic_year=academic_year)
    today = timezone.localdate()
    period_start = today - timedelta(days=29)

    if academic_year is not None:
        enrollment_qs = Enrollment.objects.filter(academic_year=academic_year)
        student_stats = enrollment_qs.aggregate(
            total=Count("student_id", distinct=True),
            active=Count(
                "student_id",
                distinct=True,
                filter=Q(status="active", student__is_active=True),
            ),
        )
        students_count = student_stats["total"] or 0
        active_students = student_stats["active"] or 0
        sections_count = Section.objects.filter(academic_year=academic_year, is_active=True).count()
        exams_count = Exam.objects.filter(academic_year=academic_year).count() if include_secondary_metrics else 0
    else:
        students_count = active_students = sections_count = exams_count = 0
    inactive_students = max(students_count - active_students, 0)
    teachers_count = Teacher.objects.filter(school=school, is_active=True).count() if school else 0

    attendance_period = (
        build_school_attendance_period_snapshot(period_start, today, school=school, academic_year=academic_year)
        if school is not None
        else _empty_attendance_period(period_start, today)
    )
    attendance_by_day = attendance_period["days"]
    today_attendance = attendance_by_day[today]
    present_today = today_attendance["present"]
    absent_today = today_attendance["absent"]
    departed_today = today_attendance["departed"]
    attendance_total_today = today_attendance["roster_total"]
    attendance_percent = today_attendance["percent"]
    attendance_data_available = today_attendance["has_data"]
    attendance_submitted_sections = today_attendance["submitted_sections"]
    attendance_pending_sections = today_attendance["pending_sections"]
    attendance_unregistered_exceptions = today_attendance["unregistered_exceptions"]
    period_absences = attendance_period["totals"]["absent"]
    period_departures = attendance_period["totals"]["departed"]
    attendance_period_data_available = attendance_period["totals"]["has_data"]

    finance = _financial_snapshot(today=today, academic_year=academic_year)

    mark_values = []
    if academic_year is not None:
        mark_values = list(
            StudentMark.objects.filter(
                exam__academic_year=academic_year,
                exam__status__in=OFFICIAL_EXAM_STATUSES,
                exam__is_active=True,
            ).values_list("mark", "exam__max_mark", "exam__pass_percentage")
        )
    percentages = []
    passed_marks = 0
    for mark, maximum, pass_percentage in mark_values:
        maximum = Decimal(maximum or 0)
        percentage = (Decimal(mark or 0) * Decimal("100") / maximum) if maximum else Decimal("0")
        percentages.append(percentage)
        if percentage >= Decimal(pass_percentage or 0):
            passed_marks += 1
    marks_count = len(percentages)
    academic_average = (
        (sum(percentages, Decimal("0")) / marks_count).quantize(Decimal("0.01"))
        if marks_count else Decimal("0.00")
    )
    pass_rate = round((passed_marks / marks_count) * 100, 1) if marks_count else 0
    academic_data_available = marks_count > 0

    attendance_trend = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        daily = attendance_by_day[day]
        attendance_trend.append({"date": day.strftime("%m-%d"), "percent": daily["percent"], "has_data": daily["has_data"]})

    financial_watch = []
    if include_financial_watch and academic_year is not None:
        financial_watch = list(
            StudentInvoice.objects.filter(academic_year=academic_year)
            .exclude(status__in=["paid", "cancelled"])
            .values("student_id", "student__full_name", "student__student_number")
            .annotate(total_due=Sum(F("amount") - F("discount_amount")))
            .order_by("-total_due")[:8]
        )

    attendance_watch = []
    if include_attendance_watch:
        exception_counts = Counter()
        for daily in attendance_by_day.values():
            exception_counts.update(daily["absent_student_ids"])
            exception_counts.update(daily["departed_student_ids"])
        watched_ids = [student_id for student_id, _count in exception_counts.most_common(8)]
        watched_students = {
            row["id"]: row
            for row in Student.objects.filter(pk__in=watched_ids).values("id", "full_name", "student_number")
        }
        attendance_watch = [
            {
                "student_id": student_id,
                "student__full_name": watched_students.get(student_id, {}).get("full_name", "-"),
                "student__student_number": watched_students.get(student_id, {}).get("student_number", "-"),
                "risk_events": exception_counts[student_id],
            }
            for student_id in watched_ids
        ]

    absent_students_today = []
    if today_attendance["absent_student_ids"]:
        absent_students_today = list(
            Attendance.objects.filter(
                date=today,
                status="absent",
                student_id__in=today_attendance["absent_student_ids"],
                academic_year=academic_year,
            )
            .select_related("student", "grade", "section")
            .order_by("student__full_name")
        )
    absent_teachers_today = list(
        TeacherAbsence.objects.filter(
            date=today,
            attendance_status="absent",
            teacher__school=school,
            teacher__is_active=True,
        )
        .select_related("teacher")
        .order_by("teacher__full_name")
    ) if school else []

    satisfaction = feedback_satisfaction_snapshot(today=today, school=school)
    teacher_evaluations = monthly_teacher_evaluation_snapshot(today=today, school=school)

    return {
        **satisfaction,
        **teacher_evaluations,
        **finance,
        "dashboard_school": school,
        "dashboard_academic_year": academic_year,
        "dashboard_scope_available": bool(school and academic_year),
        "dashboard_data_as_of": timezone.now(),
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
        "departed_today": departed_today,
        "attendance_total_today": attendance_total_today,
        "attendance_percent": attendance_percent,
        "attendance_data_available": attendance_data_available,
        "attendance_submitted_sections": attendance_submitted_sections,
        "attendance_pending_sections": attendance_pending_sections,
        "attendance_unregistered_exceptions": attendance_unregistered_exceptions,
        "period_absences": period_absences,
        "period_departures": period_departures,
        "attendance_period_data_available": attendance_period_data_available,
        "academic_average": academic_average,
        "pass_rate": pass_rate,
        "marks_count": marks_count,
        "academic_data_available": academic_data_available,
        "issued_documents": (
            IssuedDocument.objects.filter(student__enrollments__academic_year=academic_year).distinct().count()
            if include_secondary_metrics and academic_year is not None else 0
        ),
        "attendance_trend": attendance_trend,
        "financial_watch": financial_watch,
        "attendance_watch": attendance_watch,
        "absent_students_today": absent_students_today,
        "absent_teachers_today": absent_teachers_today,
    }


def _feedback_scope(school):
    qs = FeedbackTicket.objects.all()
    if school is None:
        return qs.none()
    return qs.filter(
        Q(school=school)
        | Q(school__isnull=True, sender__profile__school=school)
        | Q(school__isnull=True, sender__teacher_profile__school=school)
        | Q(school__isnull=True, sender__family_account__school=school)
    ).distinct()


def build_dashboard_context(request=None, *, school=None, academic_year=None):
    school, current_year = _resolve_scope(request=request, school=school, academic_year=academic_year)
    snapshot = build_executive_snapshot(
        school=school,
        academic_year=current_year,
        include_secondary_metrics=False,
        include_financial_watch=False,
        include_attendance_watch=False,
    )
    feedback_status = _feedback_scope(school).aggregate(
        new=Count("id", filter=Q(status="new")),
        review=Count("id", filter=Q(status="review")),
    )
    active_announcement = Announcement.objects.filter(is_active=True).order_by("-created_at").first()
    active_announcements = Announcement.objects.filter(is_active=True).count()
    if request is not None:
        request._opal_active_announcement = active_announcement

    from timetable.live_services import management_live_status
    from exams.analytics import top_students_by_grade

    top_students = top_students_by_grade(academic_year=current_year) if current_year else []
    top_students_by_grade_id = {group["grade"].pk: group for group in top_students}
    dashboard_grades = list(
        Grade.objects.filter(school=school, is_active=True, is_kindergarten=False)
        .order_by("order", "name")[:12]
    ) if school else []
    top_students_matrix = []
    for grade in dashboard_grades:
        group = top_students_by_grade_id.get(grade.pk, {"students": []})
        leaders = [row for row in group.get("students", []) if row.get("rank") == 1]
        top_students_matrix.append({"grade": grade, "leaders": leaders})

    latest_students = []
    if current_year is not None:
        latest_enrollments = Enrollment.objects.filter(
            academic_year=current_year,
            status="active",
            student__is_active=True,
        ).select_related("student", "grade", "section").order_by("-joined_at", "-pk")[:10]
        latest_students = [
            {
                "student": enrollment.student,
                "grade": enrollment.grade,
                "section": enrollment.section,
                "joined_at": enrollment.joined_at,
            }
            for enrollment in latest_enrollments
        ]

    from accounting.previous_debt_services import previous_debt_summary

    previous_debt_report = (
        previous_debt_summary(school=school, academic_year=current_year)
        if school and current_year else {"total": Decimal("0.00"), "guardians_count": 0, "students_count": 0}
    )

    snapshot.update({
        "students": snapshot["students_count"],
        "teachers": snapshot["teachers_count"],
        "sections": snapshot["sections_count"],
        "exams": snapshot["exams_count"],
        "total_income": snapshot["paid_amount"],
        "total_unpaid": snapshot["outstanding"],
        "previous_debt_total": previous_debt_report["total"],
        "previous_debt_guardians_count": previous_debt_report["guardians_count"],
        "previous_debt_students_count": previous_debt_report["students_count"],
        "latest_students": latest_students,
        "top_students_by_grade": top_students,
        "top_students_matrix": top_students_matrix,
        "top_students_year": current_year,
        "new_feedback_count": feedback_status["new"] or 0,
        "review_feedback_count": feedback_status["review"] or 0,
        # Broadcasts and announcements are system-wide models in the current
        # schema; these are exact active-record counts, not estimates.
        "active_broadcasts": BroadcastMessage.objects.filter(is_active=True).count(),
        "active_announcements": active_announcements,
        "active_announcement": active_announcement,
        "opal_live_schedule": management_live_status(school) if school else {
            "message": "لا توجد مدرسة نشطة",
            "seconds_remaining": None,
            "busy_rows": [],
            "busy_teachers": 0,
            "free_teachers": [],
            "free_teachers_count": 0,
            "teacher_state_active": False,
            "teacher_state_message": "لا يمكن حساب الحالة الحية دون مدرسة نشطة.",
            "grade_rows": [],
            "grade_columns": [],
        },
    })
    return snapshot


def build_executive_export_rows(snapshot=None, *, request=None, school=None, academic_year=None):
    snapshot = snapshot or build_executive_snapshot(request=request, school=school, academic_year=academic_year)
    attendance_value = f'{snapshot["attendance_percent"]}%' if snapshot.get("attendance_data_available", False) else "لا توجد سجلات معتمدة"
    collection_value = f'{snapshot["collection_rate"]}%' if snapshot.get("finance_data_available", False) else "لا توجد رسوم للعام الحالي"
    success_value = f'{snapshot["pass_rate"]}%' if snapshot.get("academic_data_available", False) else "لا توجد علامات رسمية"
    return [
        ("المدرسة", snapshot.get("dashboard_school") or "-"),
        ("العام الدراسي", snapshot.get("dashboard_academic_year") or "-"),
        ("تاريخ التقرير", snapshot["today"]),
        ("طلاب العام الحالي", snapshot["students_count"]),
        ("الطلاب النشطون", snapshot["active_students"]),
        ("المعلمون النشطون", snapshot["teachers_count"]),
        ("الشعب النشطة", snapshot["sections_count"]),
        ("نسبة الحضور اليوم", attendance_value),
        ("غيابات آخر 30 يومًا", snapshot["period_absences"]),
        ("مغادرات آخر 30 يومًا", snapshot["period_departures"]),
        ("إجمالي الرسوم الصافية", snapshot["total_invoices"]),
        ("إجمالي الدفعات المعتمدة", snapshot["paid_amount"]),
        ("إجمالي المتبقي", snapshot["outstanding"]),
        ("نسبة التحصيل", collection_value),
        ("الرسوم المتأخرة", snapshot["overdue_invoices"]),
        ("متوسط العلامات الرسمية", snapshot["academic_average"]),
        ("نسبة العلامات المجتازة", success_value),
        ("الوثائق المصدرة", snapshot["issued_documents"]),
    ]


def build_attendance_detail_context(*, request=None, school=None, academic_year=None):
    snapshot = build_executive_snapshot(
        request=request,
        school=school,
        academic_year=academic_year,
        include_secondary_metrics=False,
        include_financial_watch=False,
        include_attendance_watch=True,
    )
    return {
        "today": snapshot["today"],
        "period_start": snapshot["period_start"],
        "present_today": snapshot["present_today"],
        "absent_today": snapshot["absent_today"],
        "departed_today": snapshot["departed_today"],
        "attendance_total_today": snapshot["attendance_total_today"],
        "attendance_percent": snapshot["attendance_percent"],
        "attendance_data_available": snapshot["attendance_data_available"],
        "attendance_submitted_sections": snapshot["attendance_submitted_sections"],
        "attendance_pending_sections": snapshot["attendance_pending_sections"],
        "attendance_unregistered_exceptions": snapshot["attendance_unregistered_exceptions"],
        "attendance_trend": snapshot["attendance_trend"],
        "attendance_watch": snapshot["attendance_watch"],
        "absent_students_today": snapshot["absent_students_today"],
        "absent_teachers_today": snapshot["absent_teachers_today"],
        "dashboard_school": snapshot["dashboard_school"],
        "dashboard_academic_year": snapshot["dashboard_academic_year"],
    }
