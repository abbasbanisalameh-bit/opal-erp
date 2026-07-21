from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .workflow import (
    build_attendance_dashboard_context,
    build_attendance_report_context,
    parse_attendance_date,
    update_attendance_lock,
)


@staff_member_required
def attendance_dashboard(request):
    return render(
        request,
        "attendance_v2/dashboard.html",
        build_attendance_dashboard_context(),
    )


@staff_member_required
def take_attendance(request):
    messages.info(request, "تسجيل الغياب اليومي متاح من بوابة مربي الصف فقط. هذه الشاشة مخصصة للتقرير والمتابعة الإدارية.")
    return redirect("attendance_v2:report")


@staff_member_required
def attendance_report(request):
    return render(
        request,
        "attendance_v2/report.html",
        build_attendance_report_context(params=request.GET),
    )


@staff_member_required
@require_POST
def attendance_lock(request):
    selected_date = parse_attendance_date(request.POST.get("date"))
    result = update_attendance_lock(
        request=request,
        selected_date=selected_date,
        section_id=request.POST.get("section"),
        action=request.POST.get("action", "lock"),
    )
    messages.success(
        request,
        f"تم {'قفل' if result['is_locked'] else 'فتح'} {result['count']} سجل حضور.",
    )
    if result["skipped_closed"]:
        messages.warning(
            request,
            f"بقي {result['skipped_closed']} سجلًا مقفلًا لأنه يتبع عامًا دراسيًا مغلقًا.",
        )
    return redirect("attendance_v2:report")
