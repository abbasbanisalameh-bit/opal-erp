from __future__ import annotations

import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from enterprise_ops.services import audit

from .backup_file_actions import append_operation_log, superuser_required


STANDARD_DOMAIN_RE = re.compile(
    r"^(?P<username>[a-z0-9][a-z0-9-]*)\.(?P<region>pythonanywhere\.com|eu\.pythonanywhere\.com)$",
    re.IGNORECASE,
)
SAFE_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$", re.IGNORECASE)
SAFE_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
SAFE_WSGI_NAME_RE = re.compile(r"^[a-zA-Z0-9_.-]+_wsgi\.py$")


class WebAppReloadError(RuntimeError):
    """A safe reload error that can be displayed to the system administrator."""


@dataclass(frozen=True)
class WebAppReloadResult:
    ok: bool
    message: str
    method: str
    domain: str


def _clean_host(value: str) -> str:
    host = (value or "").strip().lower().split(":", 1)[0].rstrip(".")
    return host if SAFE_DOMAIN_RE.fullmatch(host) else ""


def _resolve_domain(request_host: str = "") -> str:
    configured = _clean_host(os.environ.get("OPAL_PYTHONANYWHERE_DOMAIN", ""))
    if configured:
        return configured
    detected = _clean_host(request_host)
    if detected and STANDARD_DOMAIN_RE.fullmatch(detected):
        return detected
    raise WebAppReloadError(
        "تعذر تحديد موقع PythonAnywhere. أضف OPAL_PYTHONANYWHERE_DOMAIN إلى متغيرات البيئة."
    )


def _resolve_username(domain: str) -> str:
    configured = os.environ.get("OPAL_PYTHONANYWHERE_USERNAME", "").strip()
    if configured:
        if not SAFE_USERNAME_RE.fullmatch(configured):
            raise WebAppReloadError("اسم مستخدم PythonAnywhere في الإعدادات غير صالح.")
        return configured
    match = STANDARD_DOMAIN_RE.fullmatch(domain)
    if match:
        return match.group("username")
    raise WebAppReloadError(
        "أضف OPAL_PYTHONANYWHERE_USERNAME عند استخدام نطاق مخصص."
    )


def _api_host(domain: str) -> str:
    configured = _clean_host(os.environ.get("OPAL_PYTHONANYWHERE_API_HOST", ""))
    if configured:
        return configured
    return "eu.pythonanywhere.com" if domain.endswith(".eu.pythonanywhere.com") else "www.pythonanywhere.com"


def _reload_by_api(*, username: str, domain: str, token: str) -> WebAppReloadResult:
    url = (
        f"https://{_api_host(domain)}/api/v0/user/"
        f"{urllib.parse.quote(username, safe='')}/webapps/"
        f"{urllib.parse.quote(domain, safe='')}/reload/"
    )
    request = urllib.request.Request(
        url,
        data=b"",
        method="POST",
        headers={"Authorization": f"Token {token}", "User-Agent": "OPAL-ERP-Update-Center/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = getattr(response, "status", 200)
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise WebAppReloadError("رمز API لا يملك صلاحية إعادة تحميل الموقع.") from exc
        raise WebAppReloadError(f"رفض PythonAnywhere طلب إعادة التحميل (HTTP {exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise WebAppReloadError("تعذر الاتصال بواجهة PythonAnywhere لإعادة التحميل.") from exc
    if status < 200 or status >= 300:
        raise WebAppReloadError(f"أعاد PythonAnywhere حالة غير متوقعة (HTTP {status}).")
    return WebAppReloadResult(
        ok=True,
        method="pythonanywhere_api",
        domain=domain,
        message="تم إرسال أمر إعادة تحميل الموقع إلى PythonAnywhere.",
    )


def _reload_by_wsgi_touch(*, domain: str) -> WebAppReloadResult:
    configured = os.environ.get("OPAL_PYTHONANYWHERE_WSGI_FILE", "").strip()
    raw_path = configured or f"/var/www/{domain.replace('.', '_')}_wsgi.py"
    path = Path(raw_path).expanduser()
    if not path.is_absolute() or path.parent != Path("/var/www") or not SAFE_WSGI_NAME_RE.fullmatch(path.name):
        raise WebAppReloadError("مسار WSGI المخصص لإعادة التحميل غير صالح.")
    try:
        resolved = path.resolve(strict=True)
        if resolved.parent != Path("/var/www"):
            raise WebAppReloadError("ملف WSGI خارج المسار المسموح.")
        os.utime(resolved, None)
    except FileNotFoundError as exc:
        raise WebAppReloadError(
            "ملف WSGI غير موجود. عيّن OPAL_PYTHONANYWHERE_WSGI_FILE بالمسار الصحيح."
        ) from exc
    except PermissionError as exc:
        raise WebAppReloadError("لا توجد صلاحية لتحديث وقت ملف WSGI.") from exc
    except OSError as exc:
        raise WebAppReloadError("تعذر لمس ملف WSGI لإعادة تحميل الموقع.") from exc
    return WebAppReloadResult(
        ok=True,
        method="wsgi_touch",
        domain=domain,
        message="تم إرسال أمر إعادة تحميل الموقع عبر ملف WSGI.",
    )


def reload_pythonanywhere_webapp(*, request_host: str = "") -> WebAppReloadResult:
    """Reload the configured PythonAnywhere web app without exposing its API token."""
    domain = _resolve_domain(request_host)
    token = (
        os.environ.get("OPAL_PYTHONANYWHERE_API_TOKEN", "").strip()
        or os.environ.get("API_TOKEN", "").strip()
    )
    if token:
        return _reload_by_api(
            username=_resolve_username(domain),
            domain=domain,
            token=token,
        )
    return _reload_by_wsgi_touch(domain=domain)


@superuser_required
@require_POST
def reload_webapp(request):
    try:
        result = reload_pythonanywhere_webapp(request_host=request.get_host())
    except WebAppReloadError as exc:
        message = str(exc)
        append_operation_log(f"RELOAD_FAILED | user={request.user.pk} | message={message}")
        audit(
            request,
            "update",
            "core.WebAppReload",
            description=f"فشل طلب إعادة تحميل الموقع: {message}",
        )
        return JsonResponse({"ok": False, "message": message}, status=409)

    append_operation_log(
        f"RELOAD_REQUESTED | user={request.user.pk} | method={result.method} | domain={result.domain}"
    )
    audit(
        request,
        "update",
        "core.WebAppReload",
        description=f"إعادة تحميل الموقع عبر {result.method} للنطاق {result.domain}",
    )
    return JsonResponse(asdict(result))
