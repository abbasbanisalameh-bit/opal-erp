from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET, require_POST

from .system_update_service import DEPLOYED_MARKER, private_storage_root, versions_dir


def superuser_required(view):
    return user_passes_test(
        lambda user: user.is_authenticated and user.is_active and user.is_superuser
    )(view)


def backup_root() -> Path:
    return private_storage_root().resolve()


def versions_root() -> Path:
    return versions_dir().resolve()


def iter_backup_files() -> list[Path]:
    root = backup_root()
    candidates = list(versions_root().glob("*.zip")) + list(root.glob("*.zip"))
    unique = {path.resolve(): path.resolve() for path in candidates if path.is_file()}
    return sorted(unique.values(), key=lambda path: path.stat().st_mtime, reverse=True)


def _relative_name(path: Path) -> str:
    return path.relative_to(backup_root()).as_posix()


def resolve_zip_file(raw_name: str | None) -> Path:
    raw = str(raw_name or "").strip().replace("\\", "/")
    if not raw or not raw.lower().endswith(".zip"):
        raise Http404("ملف النسخة غير صالح.")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise Http404("المسار غير مسموح.")
    root = backup_root()
    candidates = []
    if len(relative.parts) == 1:
        candidates.extend([versions_root() / relative.name, root / relative.name])
    else:
        candidates.append(root / relative)
    for candidate in candidates:
        candidate = candidate.resolve()
        if root != candidate.parent and root not in candidate.parents:
            continue
        if candidate.is_file() and candidate.suffix.lower() == ".zip":
            return candidate
    raise Http404("ملف النسخة غير موجود.")


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _is_deployed_version(path: Path) -> bool:
    marker = _read_json(backup_root() / DEPLOYED_MARKER)
    metadata = _read_json(path.with_suffix(".json"))
    marker_name = str(marker.get("version_name") or "").strip()
    record_name = str(metadata.get("version_name") or "").strip()
    return bool(marker_name and record_name and marker_name == record_name)


def append_operation_log(message: str) -> None:
    log_path = backup_root() / "system_operations.log"
    try:
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"{datetime.now().isoformat()} | {message}\n")
    except OSError:
        pass


@superuser_required
@require_GET
def backup_files_api(request):
    result = []
    for path in iter_backup_files():
        stat = path.stat()
        result.append({
            "name": _relative_name(path),
            "filename": path.name,
            "size_bytes": stat.st_size,
            "modified_timestamp": stat.st_mtime,
            "is_deployed": _is_deployed_version(path),
        })
    return JsonResponse({"files": result})


@superuser_required
@require_GET
def download_backup_file(request):
    path = resolve_zip_file(request.GET.get("name"))
    append_operation_log(f"DOWNLOAD | user={request.user.pk} | file={_relative_name(path)}")
    return FileResponse(
        path.open("rb"),
        as_attachment=True,
        filename=path.name,
        content_type="application/zip",
    )


def _delete_error(request, message: str):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": False, "message": message}, status=409)
    messages.error(request, message)
    return redirect("core:system_updates")


@superuser_required
@require_POST
def delete_backup_file(request):
    path = resolve_zip_file(request.POST.get("name"))
    files = iter_backup_files()
    if len(files) <= 1:
        return _delete_error(request, "لا يمكن حذف آخر نسخة محفوظة. أنشئ نسخة أحدث أو نزّلها أولًا.")
    if _is_deployed_version(path):
        return _delete_error(request, "لا يمكن حذف النسخة الجارية حاليًا من النظام.")
    filename = path.name
    relative_name = _relative_name(path)
    size = path.stat().st_size
    metadata_candidates = {path.with_suffix(".json"), backup_root() / f"{path.stem}.json"}
    path.unlink()
    for metadata_path in metadata_candidates:
        if metadata_path.is_file():
            metadata_path.unlink()
    append_operation_log(f"DELETE | user={request.user.pk} | file={relative_name} | size={size}")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "message": "تم حذف النسخة وملف معلوماتها بنجاح.",
            "filename": filename,
            "freed_bytes": size,
        })
    messages.success(request, f"تم حذف النسخة {filename} وتحرير مساحتها.")
    return redirect("core:system_updates")
