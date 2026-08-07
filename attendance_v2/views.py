from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from enterprise_ops.permissions import management_required

from .workflow import (
    build_attendance_dashboard_context,
    build_attendance_report_context,
    parse_attendance_date,
    update_attendance_lock,
)


@management_required
def attendance_dashboard(request):
    return render(
        request,
        "attendance_v2/dashboard.html",
        build_attendance_dashboard_context(),
    )


@management_required
def take_attendance(request):
    messages.info(request, "تسجيل الغياب اليومي متاح من بوابة مربي الصف فقط. هذه الشاشة مخصصة للتقرير والمتابعة الإدارية.")
    return redirect("attendance_v2:report")


@management_required
def attendance_report(request):
    return render(
        request,
        "attendance_v2/report.html",
        build_attendance_report_context(params=request.GET),
    )


@management_required
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


@management_required
@require_POST
def attendance_register_action(request, pk):
    from django.shortcuts import get_object_or_404
    from .models import AttendanceRegister
    from .workflow import update_register_state

    register = get_object_or_404(AttendanceRegister.objects.select_related("section"), pk=pk)
    try:
        update_register_state(
            request=request,
            register=register,
            action=request.POST.get("action", "close"),
            reason=request.POST.get("reason", ""),
        )
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "تم تحديث حالة سجل الغياب والمغادرة.")
    return redirect("attendance_v2:report")
