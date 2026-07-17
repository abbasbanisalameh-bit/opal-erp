from datetime import date as date_type

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import Enrollment, Grade, Section
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
            "present_today": counts.get("present", 0),
            "stats": stats,
        },
    )


@staff_member_required
def take_attendance(request):
    year_id = request.GET.get("academic_year") or request.POST.get("academic_year")
    grade_id = request.GET.get("grade") or request.POST.get("grade")
    section_id = request.GET.get("section") or request.POST.get("section")
    selected_date = _parse_date(request.GET.get("date") or request.POST.get("date"))

    enrollments = Enrollment.objects.filter(
        status="active",
        academic_year__is_closed=False,
    ).select_related("student", "academic_year", "grade", "section")
    if year_id:
        enrollments = enrollments.filter(academic_year_id=year_id)
    if grade_id:
        enrollments = enrollments.filter(grade_id=grade_id)
    if section_id:
        enrollments = enrollments.filter(section_id=section_id)

    existing = {
        item.student_id: item
        for item in Attendance.objects.filter(
            student_id__in=enrollments.values_list("student_id", flat=True),
            date=selected_date,
        )
    }

    if request.method == "POST":
        saved = 0
        locked = 0
        for enrollment in enrollments:
            status = request.POST.get(f"status_{enrollment.student_id}", "present")
            notes = request.POST.get(f"notes_{enrollment.student_id}", "").strip()
            excuse_reason = request.POST.get(f"excuse_{enrollment.student_id}", "").strip()
            if status == "excused" and not excuse_reason:
                excuse_reason = notes or "عذر مثبت لدى الإدارة"
            record = existing.get(enrollment.student_id)
            if record and record.is_locked:
                locked += 1
                continue
            record, _ = Attendance.objects.update_or_create(
                student=enrollment.student,
                date=selected_date,
                defaults={
                    "academic_year": enrollment.academic_year,
                    "grade": enrollment.grade,
                    "section": enrollment.section,
                    "status": status,
                    "notes": notes,
                    "excuse_reason": excuse_reason,
                    "recorded_by": record.recorded_by if record else request.user,
                    "updated_by": request.user,
                },
            )
            notify_parent_for_attendance(record)
            saved += 1
        audit(request, "update", "attendance_v2.Attendance", description=f"تسجيل حضور {saved} طالب بتاريخ {selected_date}")
        messages.success(request, f"تم حفظ حضور {saved} طالب.")
        if locked:
            messages.warning(request, f"تم تجاوز {locked} سجلًا مقفلًا.")
        query = f"?academic_year={year_id or ''}&grade={grade_id or ''}&section={section_id or ''}&date={selected_date}"
        return redirect(f"/attendance/take/{query}")

    rows = [(enrollment, existing.get(enrollment.student_id)) for enrollment in enrollments]
    sections = Section.objects.select_related("grade", "academic_year").filter(is_active=True)
    if year_id:
        sections = sections.filter(Q(academic_year_id=year_id) | Q(academic_year__isnull=True))
    if grade_id:
        sections = sections.filter(grade_id=grade_id)
    return render(
        request,
        "attendance_v2/take_attendance.html",
        {
            "academic_years": AcademicYear.objects.filter(is_closed=False).order_by("-start_date"),
            "grades": Grade.objects.filter(is_active=True),
            "sections": sections,
            "rows": rows,
            "selected_year": str(year_id or ""),
            "selected_grade": str(grade_id or ""),
            "selected_section": str(section_id or ""),
            "date": selected_date,
        },
    )


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
