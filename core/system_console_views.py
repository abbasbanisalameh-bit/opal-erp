from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.conf import settings


CONSOLE_SESSION_KEY = "opal_update_center_console_id"
CONSOLE_MAX_SECONDS = 30


def _require_console_admin(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        raise PermissionDenied("كونسول النظام متاح لمدير النظام الأعلى فقط.")


def _base_context(request, console_id: str):
    return {
        "console_id": console_id,
        "working_directory": str(Path(settings.BASE_DIR)),
        "max_seconds": CONSOLE_MAX_SECONDS,
    }


@login_required
@require_POST
def open_system_console(request):
    """Invalidate the previous browser console and create a fresh console session."""
    _require_console_admin(request)
    console_id = uuid.uuid4().hex
    request.session[CONSOLE_SESSION_KEY] = console_id
    request.session.modified = True
    return redirect("core:system_console")


@login_required
def system_console(request):
    _require_console_admin(request)
    console_id = request.session.get(CONSOLE_SESSION_KEY)
    if not console_id:
        console_id = uuid.uuid4().hex
        request.session[CONSOLE_SESSION_KEY] = console_id
        request.session.modified = True
    return render(request, "core/system_console.html", _base_context(request, console_id))


@login_required
@require_POST
def run_system_console(request):
    _require_console_admin(request)
    expected_id = request.session.get(CONSOLE_SESSION_KEY)
    console_id = request.POST.get("console_id", "")
    if not expected_id or console_id != expected_id:
        return JsonResponse({"ok": False, "closed": True, "error": "تم إغلاق هذه الجلسة وفتح كونسول جديد."}, status=409)

    command = (request.POST.get("command") or "").strip()
    if not command:
        return JsonResponse({"ok": True, "stdout": "", "stderr": "", "returncode": 0})

    # Guard only the most obviously catastrophic commands. This is still a privileged shell.
    lowered = command.lower().replace("\\", "/")
    blocked = (
        "rm -rf /",
        "rm -rf /*",
        "git reset --hard",
        "git clean -fd",
        "drop database",
        "drop table",
    )
    if any(item in lowered for item in blocked):
        return JsonResponse({"ok": False, "error": "تم حظر هذا الأمر من كونسول الويب لحماية نظام OPAL. نفّذ العمليات التدميرية خارج الكونسول بعد مراجعة مستقلة."}, status=400)

    env = os.environ.copy()
    try:
        result = subprocess.run(
            ["bash", "-lc", command],
            cwd=str(settings.BASE_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=CONSOLE_MAX_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        return JsonResponse({
            "ok": False,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + f"\nانتهت مهلة الأمر بعد {CONSOLE_MAX_SECONDS} ثانية.",
            "returncode": 124,
        })
    except Exception as exc:
        return JsonResponse({"ok": False, "stdout": "", "stderr": str(exc), "returncode": 1}, status=500)

    return JsonResponse({
        "ok": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    })
