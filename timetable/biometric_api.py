from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .biometric_services import authenticate_device_token, ingest_punches


def _response(data=None, *, status=200, error=None):
    payload = {"ok": error is None}
    if error is None:
        payload["data"] = data or {}
    else:
        payload["error"] = {"message": str(error)}
    response = JsonResponse(payload, status=status, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "no-store"
    return response


@csrf_exempt
@require_POST
def biometric_punch_ingest(request):
    raw_token = (request.headers.get("X-OPAL-BIOMETRIC-TOKEN") or "").strip()
    if not raw_token:
        auth = (request.headers.get("Authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            raw_token = auth.split(" ", 1)[1].strip()
    device = authenticate_device_token(raw_token)
    if device is None:
        return _response(status=401, error="رمز ربط جهاز البصمة غير صحيح أو الجهاز غير فعال.")
    try:
        payload = json.loads((request.body or b"{}").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _response(status=400, error="JSON غير صالح.")
    events = payload.get("events") if isinstance(payload, dict) else None
    try:
        result = ingest_punches(device, events)
    except ValidationError as exc:
        message = " ".join(exc.messages) if getattr(exc, "messages", None) else str(exc)
        return _response(status=400, error=message)
    return _response({"device": device.device_code, **result}, status=201)
