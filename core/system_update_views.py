from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse

from .system_update_service import (
    SystemUpdateError,
    create_current_snapshot,
    get_current_version,
    get_git_status,
    get_github_versions,
    list_local_versions,
    max_package_bytes,
    private_storage_root,
    push_current_system_to_github,
    restore_github_version,
    restore_local_version,
    save_uploaded_update,
)
from .update_engine_runtime import CONFIRMATION_WORD


def _redirect_tab(tab: str):
    return redirect(f"{reverse('core:system_updates')}?tab={tab}")


@login_required
def system_updates(request):
    if not request.user.is_superuser:
        raise PermissionDenied("هذه الصفحة متاحة لمدير النظام الأعلى فقط.")

    if request.method == "POST":
        action = request.POST.get("action", "")
        tab = request.POST.get("tab", "local")
        username = request.user.get_username()
        try:
            if action == "create_current_snapshot":
                record = create_current_snapshot(
                    username=username,
                    version_name=request.POST.get("version_name", ""),
                )
                messages.success(
                    request,
                    f"تم حفظ نسخة الكود الحالية: {record.version_name} — {record.filename}",
                )
            elif action == "upload_update":
                record = save_uploaded_update(
                    request.FILES.get("update_file"),
                    username=username,
                )
                messages.success(
                    request,
                    f"تم رفع التحديث والتحقق منه وحفظه: {record.version_name}",
                )
            elif action in {"restore_local", "install_local"}:
                # The Update Center confirmation is handled by the UI.  Keep the
                # engine's existing confirmation contract without asking the user
                # to type a special word.
                result = restore_local_version(
                    filename=request.POST.get("filename", ""),
                    username=username,
                    confirmation=CONFIRMATION_WORD,
                )
                messages.success(
                    request,
                    f"{result.message} النسخة: {result.version_name}. "
                    f"نسخة أمان الكود: {result.safety_snapshot}. "
                    f"نقطة أمان قاعدة البيانات: {result.database_safety_snapshot}. "
                    "اضغط Reload من صفحة Web.",
                )
            elif action == "push_github":
                result = push_current_system_to_github(username=username)
                messages.success(
                    request,
                    f"{result.message} الفرع: {result.branch} — Commit: {result.commit}",
                )
                tab = "github"
            elif action == "refresh_github":
                count = len(get_github_versions(fetch=True))
                messages.success(request, f"تم تحديث بيانات GitHub. عدد النسخ المعروضة: {count}.")
                tab = "github"
            elif action in {"restore_github", "install_github"}:
                result = restore_github_version(
                    ref=request.POST.get("ref", ""),
                    username=username,
                    confirmation=CONFIRMATION_WORD,
                )
                messages.success(
                    request,
                    f"{result.message} نسخة GitHub: {result.version_name}. "
                    f"نسخة أمان الكود: {result.safety_snapshot}. "
                    f"نقطة أمان قاعدة البيانات: {result.database_safety_snapshot}. "
                    "اضغط Reload من صفحة Web.",
                )
                tab = "github"
            else:
                messages.error(request, "العملية المطلوبة غير معروفة.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        except SystemUpdateError as exc:
            messages.error(request, str(exc))
        except Exception:
            messages.error(
                request,
                "حدث خطأ غير متوقع. راجع سجل الخادم قبل إعادة المحاولة.",
            )
        return _redirect_tab(tab)

    active_tab = request.GET.get("tab", "local")
    if active_tab not in {"local", "github"}:
        active_tab = "local"
    return render(
        request,
        "core/system_updates.html",
        {
            "active_tab": active_tab,
            "current_version": get_current_version(),
            "local_versions": list_local_versions(),
            "git_status": get_git_status(),
            "github_versions": get_github_versions(fetch=False),
            "package_limit_mb": max_package_bytes() // (1024 * 1024),
            "storage_directory": str(private_storage_root()),
        },
    )
