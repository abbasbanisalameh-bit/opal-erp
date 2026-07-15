from __future__ import annotations

from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.http import FileResponse, Http404, JsonResponse
from django.views.decorators.http import require_GET, require_POST


def superuser_required(view):
    return user_passes_test(
        lambda user: user.is_authenticated
        and user.is_active
        and user.is_superuser
    )(view)


def backup_root() -> Path:
    configured_names = (
        "OPAL_PRIVATE_BACKUPS_DIR",
        "OPAL_BACKUPS_DIR",
        "SYSTEM_BACKUPS_DIR",
    )

    for setting_name in configured_names:
        configured = getattr(settings, setting_name, None)

        if configured:
            root = Path(configured).expanduser()
            root.mkdir(parents=True, exist_ok=True)
            return root.resolve()

    root = Path.home() / "opal_private_backups"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def resolve_zip_file(raw_name: str | None) -> Path:
    name = Path(raw_name or "").name

    if not name or not name.lower().endswith(".zip"):
        raise Http404("ملف النسخة غير صالح.")

    root = backup_root()
    path = (root / name).resolve()

    if path.parent != root:
        raise Http404("المسار غير مسموح.")

    if not path.is_file():
        raise Http404("ملف النسخة غير موجود.")

    return path


def append_operation_log(message: str) -> None:
    log_path = backup_root() / "system_operations.log"

    try:
        with log_path.open("a", encoding="utf-8") as log:
            log.write(
                f"{datetime.now().isoformat()} | {message}\n"
            )
    except OSError:
        pass


@superuser_required
@require_GET
def backup_files_api(request):
    root = backup_root()

    files = sorted(
        root.glob("*.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    result = []

    for path in files:
        stat = path.stat()

        result.append(
            {
                "name": path.name,
                "size_bytes": stat.st_size,
                "modified_timestamp": stat.st_mtime,
            }
        )

    return JsonResponse({"files": result})


@superuser_required
@require_GET
def download_backup_file(request):
    path = resolve_zip_file(request.GET.get("name"))

    append_operation_log(
        f"DOWNLOAD | user={request.user.pk} | file={path.name}"
    )

    return FileResponse(
        path.open("rb"),
        as_attachment=True,
        filename=path.name,
        content_type="application/zip",
    )


@superuser_required
@require_POST
def delete_backup_file(request):
    path = resolve_zip_file(request.POST.get("name"))
    filename = path.name
    size = path.stat().st_size

    # حذف ملف ZIP
    path.unlink()

    # حذف ملف المعلومات المرتبط بالنسخة
    metadata_path = path.with_suffix(".json")

    if metadata_path.is_file():
        metadata_path.unlink()

    append_operation_log(
        "DELETE | "
        f"user={request.user.pk} | "
        f"file={filename} | "
        f"size={size}"
    )

    return JsonResponse(
        {
            "ok": True,
            "message": "تم حذف النسخة وملف معلوماتها بنجاح.",
            "filename": filename,
            "freed_bytes": size,
        }
    )
