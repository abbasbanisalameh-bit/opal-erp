"""نقطة الدخول الموحدة لدورة الحضور والانضباط في OPAL ERP.

تحافظ هذه الطبقة على السلوك الحالي وتجمع بناء لوحة الحضور والتقارير
وتعديل السجلات وقفلها وتنبيهات أولياء الأمور في موضع واحد واضح.
"""

from datetime import date as date_type, datetime, time

from django.db.models import Count, Max, Q, Window
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from academics.models import Grade, Section
from enterprise_ops.services import audit

from .analytics import build_school_attendance_period_snapshot
from .forms import AttendanceEditForm
from .models import Attendance, AttendanceRegister
from .services import notify_parent_for_attendance
from core.secondary_effects import run_secondary_effect


def parse_attendance_date(value, fallback=None):
    """تحويل قيمة تاريخ الإدخال إلى تاريخ صالح مع بديل آمن."""
    try:
        return date_type.fromisoformat(str(value))
    except (TypeError, ValueError):
        return fallback or timezone.localdate()


def build_attendance_dashboard_context(*, target_date=None):
    """بناء سياق لوحة الحضور اليومية من مصدر واحد."""
    selected_date = target_date or timezone.localdate()
    sync_attendance_registers(notify_managers=False)
    snapshot = build_school_attendance_period_snapshot(selected_date, selected_date)
    day = snapshot["days"][selected_date]
    return {
        "today": selected_date,
        "total_today": day["roster_total"],
        "present_today": day["present"],
        "absent_today": day["absent"],
        "departed_today": day["departed"],
        "attendance_percent": day["percent"],
        "submitted_sections": day["submitted_sections"],
        "pending_sections": day["pending_sections"],
        "has_data": day["has_data"],
        "unregistered_exceptions": day["unregistered_exceptions"],
        "stats": [
            {"status": "absent", "total": day["absent"]},
            {"status": "departed", "total": day["departed"]},
        ],
    }


def build_attendance_report_context(*, params):
    """تطبيق فلاتر تقرير الحضور الحالية وتجهيز سياق القالب."""
    sync_attendance_registers()
    records = Attendance.objects.select_related(
        "student", "academic_year", "grade", "section", "section__grade", "recorded_by"
    ).filter(status__in=["absent", "departed"])
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
        "registers": AttendanceRegister.objects.select_related(
            "section", "section__grade", "reviewed_by", "reopened_by"
        ).order_by("-date")[:300],
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


@transaction.atomic
def save_attendance_edit(*, request, form):
    """حفظ تعديل الحضور وإرسال التنبيه وتسجيل التدقيق."""
    record = form.save(commit=False)
    record.updated_by = request.user
    record.save()
    transaction.on_commit(
        lambda: run_secondary_effect(
            notify_parent_for_attendance,
            record,
            label="attendance edit parent notification",
        )
    )
    audit(
        request,
        "update",
        "attendance_v2.Attendance",
        record.pk,
        f"تعديل حضور {record.student.full_name} بتاريخ {record.date}",
    )
    return record, 0


def _attendance_day_end_times(school_ids):
    """Return dismissal times for many schools in one query."""
    from timetable.models import SchoolDayEvent

    rows = SchoolDayEvent.objects.filter(
        school_id__in=school_ids,
        event_type="dismissal",
        is_active=True,
    ).values("school_id").annotate(end_time=Max("end_time"))
    return {row["school_id"]: row["end_time"] for row in rows}


def sync_attendance_registers(*, notify_managers=True):
    """قفل سجلات المعلمين بعد الدوام وتنبيه الإدارة بالسجلات التي تنتظر الإغلاق النهائي."""
    from enterprise_ops.services import notify_management_batch
    from .models import Attendance, AttendanceRegister

    now = timezone.localtime()
    open_registers = list(
        AttendanceRegister.objects.select_related(
            "academic_year__school", "section__grade", "grade"
        ).filter(is_teacher_locked=False, is_admin_closed=False, date__lte=now.date())
    )
    dismissal_times = _attendance_day_end_times(
        {register.academic_year.school_id for register in open_registers}
    )
    registers_to_lock = []
    for register in open_registers:
        dismissal_time = dismissal_times.get(register.academic_year.school_id, time(14, 0))
        day_end = timezone.make_aware(
            datetime.combine(register.date, dismissal_time),
            timezone.get_current_timezone(),
        )
        if now >= day_end:
            registers_to_lock.append(register)

    if registers_to_lock:
        locked_ids = [register.pk for register in registers_to_lock]
        AttendanceRegister.objects.filter(pk__in=locked_ids).update(
            is_teacher_locked=True,
            teacher_locked_at=now,
            updated_at=now,
        )
        attendance_pairs = Q()
        for register in registers_to_lock:
            attendance_pairs |= Q(section_id=register.section_id, date=register.date)
        if attendance_pairs:
            Attendance.objects.filter(attendance_pairs).update(is_locked=True)
    else:
        locked_ids = []

    pending = AttendanceRegister.objects.select_related("section", "grade").filter(
        is_teacher_locked=True, is_admin_closed=False
    )
    if notify_managers:
        pending_rows = list(
            pending.select_related("section__grade")
            .annotate(pending_total=Window(expression=Count("pk")))[:100]
        )
        notify_management_batch([
            {
                "title": "سجل غياب ينتظر الإغلاق",
                "message": (
                    f"سجل {register.section} بتاريخ {register.date} "
                    "أُغلق للمعلم وينتظر مراجعة الإدارة."
                ),
                "level": "warning",
                "link": f"/attendance/report/?register={register.pk}",
                "event_key": f"attendance-register-pending:{register.pk}",
            }
            for register in pending_rows
        ])
        pending_count = pending_rows[0].pending_total if pending_rows else 0
    else:
        pending_count = pending.count()
    return {"auto_locked": len(locked_ids), "pending_review": pending_count}


def update_register_state(*, request, register, action, reason=""):
    """إغلاق إداري أو إعادة فتح سجل مع تسجيل التدقيق."""
    from .models import Attendance, AttendanceRegister

    now = timezone.now()
    if action == "close":
        register.is_teacher_locked = True
        register.teacher_locked_at = register.teacher_locked_at or now
        register.is_admin_closed = True
        register.admin_closed_at = now
        register.reviewed_by = request.user
        register.save(update_fields=[
            "is_teacher_locked", "teacher_locked_at", "is_admin_closed",
            "admin_closed_at", "reviewed_by", "updated_at",
        ])
        Attendance.objects.filter(section=register.section, date=register.date).update(
            is_locked=True, updated_by=request.user
        )
        action_label = "إغلاق إداري نهائي"
    elif action == "reopen":
        if not reason.strip():
            raise ValueError("سبب إعادة فتح السجل مطلوب.")
        register.is_teacher_locked = False
        register.teacher_locked_at = None
        register.is_admin_closed = False
        register.admin_closed_at = None
        register.reopened_by = request.user
        register.reopen_reason = reason.strip()
        register.save(update_fields=[
            "is_teacher_locked", "teacher_locked_at", "is_admin_closed",
            "admin_closed_at", "reopened_by", "reopen_reason", "updated_at",
        ])
        Attendance.objects.filter(section=register.section, date=register.date).update(
            is_locked=False, updated_by=request.user
        )
        action_label = "إعادة فتح"
    else:
        raise ValueError("إجراء غير صالح.")

    audit(
        request,
        "update",
        "attendance_v2.AttendanceRegister",
        register.pk,
        f"{action_label} سجل {register.section} بتاريخ {register.date}. {reason}".strip(),
    )
    return register
