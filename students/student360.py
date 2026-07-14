from datetime import datetime, time

from django.db.models import Avg, Count, Sum
from django.utils import timezone

from academics.models import Enrollment, StudentGuardian
from accounting.models import StudentInvoice, StudentPayment
from admissions.financial_services import (
    find_sibling_students,
    student_payment_status,
    student_remaining,
    student_total_fees,
    student_total_paid,
)
from admissions.models import FeePaymentAllocation
from attendance_v2.models import Attendance
from documents.models import StudentIssuedDocument
from exams.models import StudentMark
from parent_portal.models import FamilyStudent
from timetable.models import TimetableEntry


def _as_aware_datetime(value):
    """Normalize date/datetime values so mixed activity rows can be sorted safely."""
    if value is None:
        return timezone.now()
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.combine(value, time.min)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _build_activity_timeline(enrollments, allocations, attendance_recent, marks, documents):
    rows = []

    for row in allocations[:20]:
        rows.append({
            "at": _as_aware_datetime(row.created_at),
            "kind": "payment",
            "icon": "cash-coin",
            "label": "دفعة مالية",
            "description": f"تم توزيع {row.amount:.2f} على حساب الطالب",
        })

    for row in attendance_recent[:20]:
        rows.append({
            "at": _as_aware_datetime(row.date),
            "kind": "attendance",
            "icon": "calendar-check",
            "label": "حضور",
            "description": f"تم تسجيل الحالة: {row.get_status_display()}",
        })

    for row in marks[:20]:
        rows.append({
            "at": _as_aware_datetime(row.created_at),
            "kind": "mark",
            "icon": "bar-chart",
            "label": "علامة جديدة",
            "description": f"{row.exam.subject}: {row.mark} من {row.exam.max_mark}",
        })

    for row in documents[:20]:
        rows.append({
            "at": _as_aware_datetime(row.created_at),
            "kind": "document",
            "icon": "file-earmark-text",
            "label": "وثيقة",
            "description": getattr(row.issued_document, "title", "تم إصدار وثيقة"),
        })

    for row in enrollments[:10]:
        rows.append({
            "at": _as_aware_datetime(getattr(row, "joined_at", None) or getattr(row, "created_at", None)),
            "kind": "academic",
            "icon": "mortarboard",
            "label": "تسجيل أكاديمي",
            "description": f"{row.academic_year} - {row.grade or '-'} / {row.section or '-'}",
        })

    rows.sort(key=lambda item: item["at"], reverse=True)
    return rows[:30]


def build_student_360_context(student):
    enrollments = list(
        Enrollment.objects.filter(student=student)
        .select_related("academic_year", "grade", "section", "section__branch")
        .order_by("-academic_year__start_date")
    )
    current_enrollment = next((row for row in enrollments if row.status == "active"), enrollments[0] if enrollments else None)

    family_link = (
        FamilyStudent.objects.filter(student=student, is_active=True)
        .select_related("family", "family__user")
        .first()
    )
    family = family_link.family if family_link else None
    siblings = list(find_sibling_students(student).exclude(pk=student.pk))
    guardian_links = list(
        StudentGuardian.objects.filter(student=student)
        .select_related("guardian")
        .order_by("-is_primary", "guardian__full_name")
    )

    invoices = list(
        StudentInvoice.objects.filter(student=student)
        .select_related("fee_category")
        .prefetch_related("payments")
        .order_by("-due_date", "-id")
    )
    payments = list(
        StudentPayment.objects.filter(invoice__student=student, status="posted")
        .select_related("invoice", "invoice__fee_category")
        .order_by("-payment_date", "-id")[:100]
    )
    allocations = list(
        FeePaymentAllocation.objects.filter(student=student)
        .select_related("fee_payment", "fee_payment__created_by")
        .order_by("-created_at")[:100]
    )

    attendance_qs = Attendance.objects.filter(student=student)
    attendance_counts = {row["status"]: row["count"] for row in attendance_qs.values("status").annotate(count=Count("id"))}
    attendance_recent = list(attendance_qs.order_by("-date")[:60])
    attendance_total = sum(attendance_counts.values())
    present_count = attendance_counts.get("present", 0)
    absent_count = attendance_counts.get("absent", 0)
    late_count = attendance_counts.get("late", 0)
    attendance_rate = round((present_count / attendance_total) * 100, 1) if attendance_total else 0

    marks_qs = StudentMark.objects.filter(student=student).select_related("exam", "exam__subject")
    mark_summary = marks_qs.aggregate(count=Count("id"), average=Avg("mark"), total_marks=Sum("mark"))
    marks = list(marks_qs.order_by("-exam__exam_date", "exam__subject__name")[:100])
    percentages = [row.percentage for row in marks]
    percentage_average = round(sum(percentages) / len(percentages), 1) if percentages else 0

    documents = list(
        StudentIssuedDocument.objects.filter(student=student)
        .select_related("issued_document", "issued_document__template")
        .order_by("-created_at")[:100]
    )

    timetable = []
    if current_enrollment and current_enrollment.section_id:
        timetable = list(
            TimetableEntry.objects.filter(
                section=current_enrollment.section,
                academic_year=current_enrollment.academic_year,
                is_active=True,
            )
            .select_related("subject", "teacher", "time_slot", "section")
            .order_by("day", "time_slot__order")
        )

    total = student_total_fees(student)
    paid = student_total_paid(student)
    remaining = student_remaining(student)
    payment_status = student_payment_status(student)
    finance = {
        "total": total,
        "paid": paid,
        "remaining": remaining,
        "status": payment_status,
        "status_label": {"paid": "مسدد بالكامل", "partial": "مسدد جزئيًا", "unpaid": "غير مسدد"}.get(payment_status, payment_status),
        "status_class": {"paid": "success", "partial": "warning", "unpaid": "danger"}.get(payment_status, "secondary"),
        "payment_rate": round((float(paid) / float(total)) * 100, 1) if total and total > 0 else 0,
    }

    completeness_fields = [
        student.national_id, student.phone, student.address, student.guardian_name,
        student.gender, student.blood_type, student.enrollment_date, current_enrollment, family,
    ]
    data_completeness = round((sum(bool(value) for value in completeness_fields) / len(completeness_fields)) * 100)

    alerts = []
    if not current_enrollment:
        alerts.append({"level": "danger", "text": "لا يوجد تسجيل أكاديمي حالي للطالب."})
    if not family:
        alerts.append({"level": "warning", "text": "الطالب غير مرتبط بحساب أسرة رسمي."})
    if remaining and remaining > 0:
        alerts.append({"level": "warning", "text": f"يوجد رصيد مالي متبقٍ بقيمة {remaining:.2f}."})
    if attendance_total >= 5 and attendance_rate < 80:
        alerts.append({"level": "danger", "text": f"نسبة الحضور منخفضة ({attendance_rate}%)."})
    if marks and percentage_average < 60:
        alerts.append({"level": "danger", "text": f"متوسط التحصيل أقل من 60% ({percentage_average}%)."})
    if not student.national_id:
        alerts.append({"level": "info", "text": "الرقم الوطني غير مسجل."})

    risk_score = 0
    risk_score += 2 if not current_enrollment else 0
    risk_score += 1 if not family else 0
    risk_score += 2 if attendance_total >= 5 and attendance_rate < 80 else 0
    risk_score += 2 if marks and percentage_average < 60 else 0
    risk_score += 1 if remaining and total and float(remaining) / float(total) >= 0.5 else 0
    if risk_score >= 5:
        risk = {"label": "مرتفع", "class": "danger", "score": risk_score}
    elif risk_score >= 2:
        risk = {"label": "متوسط", "class": "warning", "score": risk_score}
    else:
        risk = {"label": "منخفض", "class": "success", "score": risk_score}

    activity_timeline = _build_activity_timeline(enrollments, allocations, attendance_recent, marks, documents)

    return {
        "student": student,
        "enrollments": enrollments,
        "current_enrollment": current_enrollment,
        "family": family,
        "family_link": family_link,
        "siblings": siblings,
        "guardian_links": guardian_links,
        "invoices": invoices,
        "payments": payments,
        "allocations": allocations,
        "finance": finance,
        "attendance_recent": attendance_recent,
        "attendance_counts": attendance_counts,
        "attendance_total": attendance_total,
        "attendance_rate": attendance_rate,
        "absent_count": absent_count,
        "late_count": late_count,
        "marks": marks,
        "mark_summary": mark_summary,
        "percentage_average": percentage_average,
        "documents": documents,
        "timetable": timetable,
        "alerts": alerts,
        "risk": risk,
        "data_completeness": data_completeness,
        "activity_timeline": activity_timeline,
    }
