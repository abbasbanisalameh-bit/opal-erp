from decimal import Decimal

from attendance_v2.analytics import build_student_attendance_summaries
from exams.models import StudentMark
from .receipt_services import build_guardian_receipt_history
from .financial_access import guardian_feature_allowed

try:
    from documents.models import StudentIssuedDocument
except Exception:
    StudentIssuedDocument = None

from admissions.financial_services import student_finance_snapshot


def _safe_percentage(value, total):
    try:
        value = Decimal(value or 0)
        total = Decimal(total or 0)
        if total <= 0:
            return 0
        return round(float((value / total) * 100), 1)
    except Exception:
        return 0


def build_parent360_context(family, students):
    """Build a read-only Parent 360 context without schema changes."""
    students = list(students)
    student_ids = [student.pk for student in students]

    attendance_summaries = build_student_attendance_summaries(students)
    marks_allowed = guardian_feature_allowed(family, "marks")
    marks_qs = StudentMark.objects.filter(student_id__in=student_ids).select_related(
        "student", "exam", "exam__subject"
    ) if marks_allowed else StudentMark.objects.none()
    receipt_history = build_guardian_receipt_history(students)

    children = []
    total_fees = Decimal("0")
    total_paid = Decimal("0")
    total_remaining = Decimal("0")
    total_attendance_days = 0
    total_present = 0
    total_absent = 0
    total_departed = 0

    for student in students:
        finance = student_finance_snapshot(student)
        fees = Decimal(finance["total"] or 0)
        paid = Decimal(finance["paid"] or 0)
        remaining = Decimal(finance["remaining"] or 0)
        attendance = attendance_summaries.get(student.pk, {
            "total": 0,
            "present_count": 0,
            "absent_count": 0,
            "departed_count": 0,
            "rate": 0,
        })
        attendance_days = attendance["total"]
        present = attendance["present_count"]
        absent = attendance["absent_count"]
        departed = attendance["departed_count"]
        marks = list(marks_qs.filter(student=student).order_by("-exam__exam_date")[:8])
        average = round(sum(float(m.percentage) for m in marks) / len(marks), 1) if marks else None

        if remaining <= 0:
            status_class, status_label = "success", "مسدد بالكامل"
        elif paid <= 0:
            status_class, status_label = "danger", "غير مسدد"
        else:
            status_class, status_label = "warning", "سداد جزئي"

        children.append(
            {
                "student": student,
                "fees": fees,
                "paid": paid,
                "remaining": remaining,
                "paid_percentage": _safe_percentage(paid, fees),
                "finance_sources": finance,
                "status_class": status_class,
                "status_label": status_label,
                "attendance": {
                    "days": attendance_days,
                    "present": present,
                    "absent": absent,
                    "departed": departed,
                    "rate": attendance["rate"],
                },
                "marks": marks,
                "average": average,
            }
        )
        total_fees += fees
        total_paid += paid
        total_remaining += remaining
        total_attendance_days += attendance_days
        total_present += present
        total_absent += absent
        total_departed += departed

    documents_count = 0
    recent_documents = []
    if StudentIssuedDocument is not None and student_ids:
        documents_qs = StudentIssuedDocument.objects.filter(student_id__in=student_ids).select_related(
            "student", "issued_document"
        )
        documents_count = documents_qs.count()
        recent_documents = list(documents_qs.order_by("-created_at")[:8])

    alerts = []
    if total_remaining > 0:
        alerts.append({"level": "warning", "title": "رصيد مالي متبقٍ", "text": f"إجمالي المتبقي على أبناء ولي الأمر: {total_remaining:.2f}"})
    if total_absent:
        alerts.append({"level": "danger", "title": "غياب يحتاج متابعة", "text": f"إجمالي حالات الغياب المسجلة: {total_absent}"})
    if not getattr(family, "user_id", None):
        alerts.append({"level": "danger", "title": "حساب ولي الأمر غير مفعل", "text": "لا يوجد حساب دخول مرتبط بملف ولي الأمر."})
    if not getattr(family, "phone", ""):
        alerts.append({"level": "warning", "title": "بيانات اتصال ناقصة", "text": "رقم هاتف ولي الأمر غير مسجل."})

    completeness_fields = [
        bool(getattr(family, "guardian_name", "")),
        bool(getattr(family, "phone", "")),
        bool(getattr(family, "identity_number", "")),
        bool(getattr(family, "family_code", "")),
        bool(getattr(family, "user_id", None)),
        bool(students),
    ]
    completeness = round((sum(completeness_fields) / len(completeness_fields)) * 100)

    return {
        "family": family,
        "children360": children,
        "totals360": {
            "students_count": len(students),
            "fees": total_fees,
            "paid": total_paid,
            "remaining": total_remaining,
            "paid_percentage": _safe_percentage(total_paid, total_fees),
            "attendance_days": total_attendance_days,
            "present": total_present,
            "attendance_rate": _safe_percentage(total_present, total_attendance_days),
            "absent": total_absent,
            "departed": total_departed,
            "documents": documents_count,
            "payments": len(receipt_history),
        },
        "receipt_history": receipt_history,
        "recent_documents360": recent_documents,
        "alerts360": alerts,
        "profile_completeness360": completeness,
        "marks_restricted": not marks_allowed,
    }
