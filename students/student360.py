from datetime import datetime, time

from django.db.models import Avg, Count, Sum
from django.utils import timezone

from academics.models import Enrollment
from accounting.models import StudentInvoice, StudentPayment
from admissions.financial_services import (
    find_sibling_students,
    student_finance_snapshot,
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


def _build_student_timeline(enrollments, allocations, attendance_recent, marks, documents):
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


def _build_academic_profile(student):
    """Build the canonical academic enrollment view used by Student 360."""
    enrollments = list(
        Enrollment.objects.filter(student=student)
        .select_related("academic_year", "grade", "section", "section__branch")
        .order_by("-academic_year__start_date")
    )
    current_enrollment = next(
        (row for row in enrollments if row.status == "active"),
        enrollments[0] if enrollments else None,
    )
    return {
        "enrollments": enrollments,
        "current_enrollment": current_enrollment,
    }




def _build_family_profile(student):
    """Build the canonical family and guardian links used by Student 360."""
    family_link = (
        FamilyStudent.objects.filter(student=student, is_active=True)
        .select_related("family", "family__user")
        .first()
    )
    family = family_link.family if family_link else None
    siblings = list(find_sibling_students(student).exclude(pk=student.pk))
    guardian_links = list(
        FamilyStudent.objects.filter(student=student, is_active=True)
        .select_related("family")
        .order_by("family__guardian_name")
    )
    return {
        "family_link": family_link,
        "family": family,
        "siblings": siblings,
        "guardian_links": guardian_links,
    }

def _build_finance_profile(student):
    """Build the canonical financial summary used by Student 360."""
    snapshot = student_finance_snapshot(student)
    total = snapshot["total"]
    paid = snapshot["paid"]
    remaining = snapshot["remaining"]
    status = snapshot["status"]
    return {
        "total": total,
        "paid": paid,
        "remaining": remaining,
        "status": status,
        "status_label": {
            "paid": "مسدد بالكامل",
            "partial": "مسدد جزئيًا",
            "unpaid": "غير مسدد",
        }.get(status, status),
        "status_class": {
            "paid": "success",
            "partial": "warning",
            "unpaid": "danger",
        }.get(status, "secondary"),
        "payment_rate": round((float(paid) / float(total)) * 100, 1) if total and total > 0 else 0,
    }



def _build_attendance_profile(student):
    """Build the canonical attendance summary used by Student 360."""
    attendance_qs = Attendance.objects.filter(student=student)
    counts = {
        row["status"]: row["count"]
        for row in attendance_qs.values("status").annotate(count=Count("id"))
    }
    recent = list(attendance_qs.order_by("-date")[:60])
    total = sum(counts.values())
    present = counts.get("present", 0)
    absent = counts.get("absent", 0)
    late = counts.get("late", 0)
    rate = round((present / total) * 100, 1) if total else 0
    return {
        "recent": recent,
        "counts": counts,
        "total": total,
        "present_count": present,
        "absent_count": absent,
        "late_count": late,
        "rate": rate,
    }

def _build_documents_profile(student):
    """Build the canonical issued-document history used by Student 360."""
    documents = list(
        StudentIssuedDocument.objects.filter(student=student)
        .select_related("issued_document", "issued_document__template")
        .order_by("-created_at")[:100]
    )
    return {"documents": documents}


def _build_marks_profile(student):
    """Build the canonical assessment summary used by Student 360."""
    marks_qs = StudentMark.objects.filter(student=student).select_related("exam", "exam__subject")
    summary = marks_qs.aggregate(count=Count("id"), average=Avg("mark"), total_marks=Sum("mark"))
    marks = list(marks_qs.order_by("-exam__exam_date", "exam__subject__name")[:100])
    percentages = [row.percentage for row in marks]
    percentage_average = round(sum(percentages) / len(percentages), 1) if percentages else 0
    return {
        "marks": marks,
        "summary": summary,
        "percentage_average": percentage_average,
    }



def _build_student_alerts_and_risk(
    student,
    *,
    current_enrollment,
    family,
    finance,
    attendance,
    marks_profile,
):
    """Build the canonical alerts and risk indicator used by Student 360."""
    total = finance["total"]
    remaining = finance["remaining"]
    attendance_total = attendance["total"]
    attendance_rate = attendance["rate"]
    marks = marks_profile["marks"]
    percentage_average = marks_profile["percentage_average"]

    alerts = []
    if not current_enrollment:
        alerts.append({"level": "danger", "text": "لا يوجد تسجيل أكاديمي حالي للطالب."})
    if not family:
        alerts.append({"level": "warning", "text": "الطالب غير مرتبط بملف ولي أمر رسمي."})
    if remaining and remaining > 0:
        alerts.append({"level": "warning", "text": f"يوجد رصيد مالي متبقٍ بقيمة {remaining:.2f}."})
    if attendance_total >= 5 and attendance_rate < 80:
        alerts.append({"level": "danger", "text": f"نسبة الحضور منخفضة ({attendance_rate}%)."})
    if marks and percentage_average < 60:
        alerts.append({"level": "danger", "text": f"متوسط التحصيل أقل من 60% ({percentage_average}%)."})
    if student.source == "openemis" and not student.national_id:
        alerts.append({"level": "info", "text": "الرقم الوطني للطالب غير وارد من OpenEMIS."})

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

    return {"alerts": alerts, "risk": risk}


def _build_student_supporting_profile(
    student,
    *,
    current_enrollment,
    enrollments,
    attendance_profile,
    marks_profile,
    documents_profile,
    family,
):
    """Build the remaining operational records used by Student 360."""
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
        FeePaymentAllocation.objects.filter(student=student, fee_payment__is_deleted=False)
        .select_related("fee_payment", "fee_payment__created_by")
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

    completeness_fields = [
        student.phone,
        student.address,
        student.guardian_name,
        student.gender,
        student.blood_type,
        student.enrollment_date,
        current_enrollment,
        family,
    ]
    data_completeness = round(
        (sum(bool(value) for value in completeness_fields) / len(completeness_fields)) * 100
    )

    activity_timeline = _build_student_timeline(
        enrollments,
        allocations,
        attendance_profile["recent"],
        marks_profile["marks"],
        documents_profile["documents"],
    )
    return {
        "invoices": invoices,
        "payments": payments,
        "allocations": allocations,
        "timetable": timetable,
        "data_completeness": data_completeness,
        "activity_timeline": activity_timeline,
    }

def _assemble_student_360_context(
    student,
    *,
    academic_profile,
    family_profile,
    invoices,
    payments,
    allocations,
    finance,
    attendance,
    marks_profile,
    documents_profile,
    timetable,
    alert_profile,
    data_completeness,
    activity_timeline,
):
    """Assemble the canonical Student 360 payload without changing its public keys."""
    return {
        "student": student,
        "enrollments": academic_profile["enrollments"],
        "current_enrollment": academic_profile["current_enrollment"],
        "family": family_profile["family"],
        "family_link": family_profile["family_link"],
        "siblings": family_profile["siblings"],
        "guardian_links": family_profile["guardian_links"],
        "invoices": invoices,
        "payments": payments,
        "allocations": allocations,
        "finance": finance,
        "attendance_recent": attendance["recent"],
        "attendance_counts": attendance["counts"],
        "attendance_total": attendance["total"],
        "attendance_rate": attendance["rate"],
        "absent_count": attendance["absent_count"],
        "late_count": attendance["late_count"],
        "marks": marks_profile["marks"],
        "mark_summary": marks_profile["summary"],
        "percentage_average": marks_profile["percentage_average"],
        "documents": documents_profile["documents"],
        "timetable": timetable,
        "alerts": alert_profile["alerts"],
        "risk": alert_profile["risk"],
        "data_completeness": data_completeness,
        "activity_timeline": activity_timeline,
    }


def build_student_360_context(student):
    academic_profile = _build_academic_profile(student)
    current_enrollment = academic_profile["current_enrollment"]

    family_profile = _build_family_profile(student)
    family = family_profile["family"]

    attendance = _build_attendance_profile(student)
    marks_profile = _build_marks_profile(student)
    documents_profile = _build_documents_profile(student)
    finance = _build_finance_profile(student)

    supporting_profile = _build_student_supporting_profile(
        student,
        current_enrollment=current_enrollment,
        enrollments=academic_profile["enrollments"],
        attendance_profile=attendance,
        marks_profile=marks_profile,
        documents_profile=documents_profile,
        family=family,
    )

    alert_profile = _build_student_alerts_and_risk(
        student,
        current_enrollment=current_enrollment,
        family=family,
        finance=finance,
        attendance=attendance,
        marks_profile=marks_profile,
    )

    return _assemble_student_360_context(
        student,
        academic_profile=academic_profile,
        family_profile=family_profile,
        invoices=supporting_profile["invoices"],
        payments=supporting_profile["payments"],
        allocations=supporting_profile["allocations"],
        finance=finance,
        attendance=attendance,
        marks_profile=marks_profile,
        documents_profile=documents_profile,
        timetable=supporting_profile["timetable"],
        alert_profile=alert_profile,
        data_completeness=supporting_profile["data_completeness"],
        activity_timeline=supporting_profile["activity_timeline"],
    )
