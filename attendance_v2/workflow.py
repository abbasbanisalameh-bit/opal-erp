"""نقطة الدخول الموحدة لدورة الحضور والانضباط في OPAL ERP.

تحافظ هذه الطبقة على السلوك الحالي وتجمع بناء لوحة الحضور والتقارير
وتعديل السجلات وقفلها وتنبيهات أولياء الأمور في موضع واحد واضح.
"""

from datetime import date as date_type

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from academics.models import Grade, Section
from enterprise_ops.services import audit

from .forms import AttendanceEditForm
from .models import Attendance
from .services import notify_parent_for_attendance


def parse_attendance_date(value, fallback=None):
    """تحويل قيمة تاريخ الإدخال إلى تاريخ صالح مع بديل آمن."""
    try:
        return date_type.fromisoformat(str(value))
    except (TypeError, ValueError):
        return fallback or timezone.localdate()


def build_attendance_dashboard_context(*, target_date=None):
    """بناء سياق لوحة الحضور اليومية من مصدر واحد."""
    selected_date = target_date or timezone.localdate()
    records = Attendance.objects.filter(date=selected_date)
    stats = list(records.values("status").annotate(total=Count("id")))
    counts = {row["status"]: row["total"] for row in stats}
    return {
        "today": selected_date,
        "total_today": records.count(),
        "absent_today": counts.get("absent", 0),
        "late_today": counts.get("late", 0),
        "departed_today": counts.get("departed", 0),
        "present_today": counts.get("present", 0),
        "stats": stats,
    }


def build_attendance_report_context(*, params):
    """تطبيق فلاتر تقرير الحضور الحالية وتجهيز سياق القالب."""
    records = Attendance.objects.select_related(
        "student", "academic_year", "grade", "section", "recorded_by"
    )
    date_from = params.get("date_from", "")
    date_to = params.get("date_to", "")
    status = params.get("status", "")
    grade = params.get("grade", "")
    section = params.get("section", "")
    query = params.get("q", "").strip()

    if date_from:
        records = records.filter(date__gte=date_from)
    if date_to:
        records = records.filter(date__lte=date_to)
    if status:
        records = records.filter(status=status)
    if grade:
        records = records.filter(grade_id=grade)
    if section:
        records = records.filter(section_id=section)
    if query:
        records = records.filter(
            Q(student__full_name__icontains=query)
            | Q(student__student_number__icontains=query)
        )

    return {
        "records": records[:1000],
        "grades": Grade.objects.filter(is_active=True),
        "sections": Section.objects.select_related("grade").filter(is_active=True),
        "statuses": Attendance.STATUS,
        "filters": {
            "date_from": date_from,
            "date_to": date_to,
            "status": status,
            "grade": grade,
            "section": section,
            "q": query,
        },
    }


def update_attendance_lock(*, request, selected_date, section_id=None, action="lock"):
    """قفل أو فتح سجلات الحضور مع حماية الأعوام الدراسية المغلقة."""
    queryset = Attendance.objects.filter(date=selected_date)
    if section_id:
        queryset = queryset.filter(section_id=section_id)

    skipped_closed = 0
    should_lock = action == "lock"
    if not should_lock:
        skipped_closed = queryset.filter(academic_year__is_closed=True).count()
        queryset = queryset.exclude(academic_year__is_closed=True)

    count = queryset.update(is_locked=should_lock, updated_by=request.user)
    audit(
        request,
        "update",
        "attendance_v2.Attendance",
        description=f"{'قفل' if should_lock else 'فتح'} {count} سجل حضور بتاريخ {selected_date}",
    )
    return {"count": count, "skipped_closed": skipped_closed, "is_locked": should_lock}


def build_attendance_edit_state(*, request, pk):
    """تحميل سجل الحضور ونموذج التعديل مع حالة السماح بالتعديل."""
    record = get_object_or_404(Attendance, pk=pk)
    if record.academic_year_id and record.academic_year.is_closed:
        return {"record": record, "blocked_reason": "closed_year", "form": None}
    if record.is_locked and not request.user.is_superuser:
        return {"record": record, "blocked_reason": "locked", "form": None}
    return {
        "record": record,
        "blocked_reason": None,
        "form": AttendanceEditForm(request.POST or None, instance=record),
    }


def save_attendance_edit(*, request, form):
    """حفظ تعديل الحضور وإرسال التنبيه وتسجيل التدقيق."""
    record = form.save(commit=False)
    record.updated_by = request.user
    record.save()
    notifications = notify_parent_for_attendance(record)
    audit(
        request,
        "update",
        "attendance_v2.Attendance",
        record.pk,
        f"تعديل حضور {record.student.full_name} بتاريخ {record.date}",
    )
    return record, notifications
