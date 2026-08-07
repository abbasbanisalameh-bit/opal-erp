import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from .models import ProductionDataResetRun
from .production_reset import (
    PRODUCTION_RESET_CONFIRMATION,
    collect_production_reset_preview,
    execute_production_data_reset,
)


logger = logging.getLogger(__name__)


def _is_superuser(user):
    return bool(user and user.is_authenticated and user.is_superuser)


@login_required
@user_passes_test(_is_superuser)
def production_launch_preparation(request):
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key

    if request.method == "POST":
        confirmation = request.POST.get("confirmation", "").strip()
        acknowledged = request.POST.get("acknowledged") == "yes"
        preview_token = request.POST.get("preview_token", "")

        if confirmation != PRODUCTION_RESET_CONFIRMATION:
            messages.error(
                request,
                f"تعذر التنفيذ: اكتب العبارة «{PRODUCTION_RESET_CONFIRMATION}» كما هي.",
            )
            return redirect("core:production_launch_preparation")
        if not acknowledged:
            messages.error(request, "يجب تأكيد فهمك أن البيانات التشغيلية ستُحذف نهائيًا.")
            return redirect("core:production_launch_preparation")
        if not preview_token:
            messages.error(request, "المعاينة غير موجودة. حدّث الصفحة وراجع الأعداد قبل التنفيذ.")
            return redirect("core:production_launch_preparation")

        try:
            run = execute_production_data_reset(
                keep_user=request.user,
                preview_token=preview_token,
                current_session_key=session_key,
            )
        except Exception:
            logger.exception("Production data reset failed")
            messages.error(
                request,
                "تعذرت تهيئة التشغيل الفعلي. لم يُحفظ حذف جزئي، وسُجل السبب للمراجعة.",
            )
            return redirect("core:production_launch_preparation")

        messages.success(
            request,
            "اكتملت تهيئة التشغيل الفعلي. بقي حساب المدير وإعدادات المدرسة والنظام فقط.",
        )
        return redirect("core:production_reset_report", pk=run.pk)

    preview = collect_production_reset_preview(
        keep_user=request.user,
        current_session_key=session_key,
    )
    recent_runs = ProductionDataResetRun.objects.select_related("requested_by")[:10]
    return render(
        request,
        "core/production_launch_preparation.html",
        {
            "preview": preview,
            "confirmation_phrase": PRODUCTION_RESET_CONFIRMATION,
            "recent_runs": recent_runs,
        },
    )


@login_required
@user_passes_test(_is_superuser)
def production_reset_report(request, pk):
    run = get_object_or_404(
        ProductionDataResetRun.objects.select_related("requested_by"),
        pk=pk,
    )
    from .production_reset import CATEGORY_LABELS_AR

    deleted_rows = [
        {"key": key, "label": CATEGORY_LABELS_AR.get(key, key), "count": value}
        for key, value in (run.deleted_counts or {}).items()
    ]
    remaining_rows = [
        {"key": key, "label": CATEGORY_LABELS_AR.get(key, key), "count": value}
        for key, value in (run.remaining_counts or {}).items()
    ]
    return render(
        request,
        "core/production_reset_report.html",
        {"run": run, "deleted_rows": deleted_rows, "remaining_rows": remaining_rows},
    )
