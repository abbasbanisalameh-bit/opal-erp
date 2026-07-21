from datetime import date as date_type

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import Grade, Section
from core.models import AcademicYear
from enterprise_ops.services import audit

from .models import Attendance
from .services import notify_parent_for_attendance


def _parse_date(value, fallback=None):
    try:
        return date_type.fromisoformat(str(value))
    except (TypeError, ValueError):
        return fallback or timezone.localdate()


@staff_member_required
def attendance_dashboard(request):
    today = timezone.localdate()
    today_records = Attendance.objects.filter(date=today)
    stats = today_records.values("status").annotate(total=Count("id"))
    counts = {row["status"]: row["total"] for row in stats}
    return render(
        request,
        "attendance_v2/dashboard.html",
        {
            "today": today,
            "total_today": today_records.count(),
            "absent_today": counts.get("absent", 0),
            "late_today": counts.get("late", 0),
            "departed_today": counts.get("departed", 0),
            "present_today": counts.get("present", 0),
            "stats": stats,
        },
    )


@staff_member_required
def take_attendance(request):
    messages.info(request, "تسجيل الغياب اليومي متاح من بوابة مربي الصف فقط. هذه الشاشة مخصصة للتقرير والمتابعة الإدارية.")
    return redirect("attendance_v2:report")


@staff_member_required
def attendance_report(request):
    records = Attendance.objects.select_related("student", "academic_year", "grade", "section", "recorded_by")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    status = request.GET.get("status", "")
    grade = request.GET.get("grade", "")
    section = request.GET.get("section", "")
    q = request.GET.get("q", "").strip()
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
    if q:
        records = records.filter(Q(student__full_name__icontains=q) | Q(student__student_number__icontains=q))
    return render(
        request,
        "attendance_v2/report.html",
        {
            "records": records[:1000],
            "grades": Grade.objects.filter(is_active=True),
            "sections": Section.objects.select_related("grade").filter(is_active=True),
            "statuses": Attendance.STATUS,
            "filters": {"date_from": date_from, "date_to": date_to, "status": status, "grade": grade, "section": section, "q": q},
        },
    )


@staff_member_required
@require_POST
def attendance_lock(request):
    selected_date = _parse_date(request.POST.get("date"))
    section_id = request.POST.get("section")
    action = request.POST.get("action", "lock")
    qs = Attendance.objects.filter(date=selected_date)
    if section_id:
        qs = qs.filter(section_id=section_id)
    skipped_closed = 0
    if action != "lock":
        skipped_closed = qs.filter(academic_year__is_closed=True).count()
        qs = qs.exclude(academic_year__is_closed=True)
    count = qs.update(is_locked=(action == "lock"), updated_by=request.user)
    audit(request, "update", "attendance_v2.Attendance", description=f"{'قفل' if action == 'lock' else 'فتح'} {count} سجل حضور بتاريخ {selected_date}")
    messages.success(request, f"تم {'قفل' if action == 'lock' else 'فتح'} {count} سجل حضور.")
    if skipped_closed:
        messages.warning(request, f"بقي {skipped_closed} سجلًا مقفلًا لأنه يتبع عامًا دراسيًا مغلقًا.")
    return redirect("attendance_v2:report")
