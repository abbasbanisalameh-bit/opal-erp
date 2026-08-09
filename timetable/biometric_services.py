"""Vendor-neutral biometric attendance gateway for teacher work evidence.

Fingerprint templates remain on the physical terminal. OPAL receives only a
terminal-local user id, a timestamp and an optional in/out direction. Raw
punches are evidence; they never create a daily "present" row. Suggested
exceptions are reviewed before they affect the canonical TeacherAbsence model.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import date, datetime, time, timedelta, timezone as datetime_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from teachers.models import Teacher

from .attendance_services import sync_absence_coverages
from .models import (
    BiometricDailySummary,
    BiometricDevice,
    TeacherAbsence,
    TeacherBiometricIdentity,
    TeacherBiometricPunch,
    TimetableEntry,
)

DAY_CODES = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"}


def _token_hash(raw_token: str) -> str:
    return hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()


def issue_device_token(device: BiometricDevice) -> str:
    raw = "opal_bio_" + secrets.token_urlsafe(36)
    device.token_hash = _token_hash(raw)
    device.token_hint = raw[-8:]
    device.save(update_fields=["token_hash", "token_hint", "updated_at"])
    return raw


def authenticate_device_token(raw_token: str) -> BiometricDevice | None:
    if not raw_token:
        return None
    return BiometricDevice.objects.filter(token_hash=_token_hash(raw_token), is_active=True).select_related("school", "branch").first()


def _device_zone(device: BiometricDevice):
    try:
        return ZoneInfo(device.timezone_name or "Asia/Amman")
    except ZoneInfoNotFoundError:
        return timezone.get_current_timezone()


def parse_punch_datetime(device: BiometricDevice, value) -> datetime:
    if not value:
        raise ValidationError("وقت البصمة مطلوب.")
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValidationError(f"وقت البصمة غير صالح: {value}") from exc
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=_device_zone(device))
    return parsed.astimezone(datetime_timezone.utc)


def normalize_direction(value) -> str:
    raw = str(value or "unknown").strip().lower()
    aliases = {
        "0": "in", "checkin": "in", "check-in": "in", "entry": "in", "enter": "in", "in": "in",
        "1": "out", "checkout": "out", "check-out": "out", "exit": "out", "leave": "out", "out": "out",
    }
    return aliases.get(raw, "unknown")


def event_uid_for(device: BiometricDevice, *, device_user_id: str, punched_at: datetime, direction: str, supplied_uid="") -> str:
    supplied = str(supplied_uid or "").strip()
    if supplied:
        return hashlib.sha256(f"{device.pk}:{supplied}".encode()).hexdigest()
    stable = f"{device.pk}|{device_user_id}|{punched_at.isoformat()}|{direction}"
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


@transaction.atomic
def ingest_punches(device: BiometricDevice, events) -> dict:
    if not isinstance(events, list):
        raise ValidationError("يجب إرسال events كمصفوفة.")
    accepted = duplicates = unmapped = 0
    dates = set()
    for raw_event in events[:2000]:
        if not isinstance(raw_event, dict):
            continue
        device_user_id = str(raw_event.get("user_id") or raw_event.get("device_user_id") or "").strip()
        if not device_user_id:
            raise ValidationError("معرف المستخدم داخل جهاز البصمة مطلوب.")
        punched_at = parse_punch_datetime(device, raw_event.get("timestamp") or raw_event.get("punched_at"))
        direction = normalize_direction(raw_event.get("direction") if "direction" in raw_event else raw_event.get("punch"))
        uid = event_uid_for(
            device,
            device_user_id=device_user_id,
            punched_at=punched_at,
            direction=direction,
            supplied_uid=raw_event.get("event_uid") or raw_event.get("uid"),
        )
        identity = TeacherBiometricIdentity.objects.filter(
            device=device, device_user_id=device_user_id, is_active=True
        ).select_related("teacher").first()
        defaults = {
            "teacher": identity.teacher if identity else None,
            "device_user_id": device_user_id,
            "punched_at": punched_at,
            "direction": direction,
            "raw_payload": json.loads(json.dumps(raw_event, default=str)) if raw_event else {},
        }
        _punch, created = TeacherBiometricPunch.objects.get_or_create(
            event_uid=uid,
            defaults={"device": device, **defaults},
        )
        if not created:
            duplicates += 1
            continue
        accepted += 1
        if identity is None:
            unmapped += 1
        local_day = timezone.localtime(punched_at, _device_zone(device)).date()
        dates.add(local_day)
    device.last_seen_at = timezone.now()
    device.save(update_fields=["last_seen_at", "updated_at"])
    for day in dates:
        rebuild_daily_summaries(day, school=device.school)
    return {"accepted": accepted, "duplicates": duplicates, "unmapped": unmapped, "dates": sorted(day.isoformat() for day in dates)}


def expected_teacher_window(teacher: Teacher, day: date):
    entries = list(
        TimetableEntry.objects.filter(
            teacher=teacher,
            academic_year__is_current=True,
            is_active=True,
            day=DAY_CODES[day.weekday()],
        ).select_related("time_slot").order_by("time_slot__start_time")
    )
    if not entries:
        return None, None
    return entries[0].time_slot.start_time, max(item.time_slot.end_time for item in entries)


def _day_bounds(day: date, tz):
    start = datetime.combine(day, time.min).replace(tzinfo=tz)
    end = start + timedelta(days=1)
    return start.astimezone(datetime_timezone.utc), end.astimezone(datetime_timezone.utc)


def _time_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _derive_status(*, count, first_time, last_time, expected_start, expected_end, late_grace, early_grace):
    if expected_start is None or expected_end is None:
        return "no_schedule"
    if count == 0:
        return "no_punch"
    if count == 1:
        return "incomplete"
    late = _time_minutes(first_time) > _time_minutes(expected_start) + late_grace
    early = _time_minutes(last_time) < _time_minutes(expected_end) - early_grace
    if late and early:
        return "late_and_early"
    if late:
        return "late"
    if early:
        return "early_departure"
    return "normal"


@transaction.atomic
def rebuild_daily_summaries(day: date, *, school=None, late_grace_minutes=10, early_grace_minutes=10):
    teacher_qs = Teacher.objects.filter(is_active=True, biometric_identities__is_active=True).distinct()
    if school is not None:
        teacher_qs = teacher_qs.filter(school=school)
    summaries = []
    for teacher in teacher_qs.select_related("school"):
        tz = timezone.get_current_timezone()
        device = BiometricDevice.objects.filter(teacher_identities__teacher=teacher, teacher_identities__is_active=True).first()
        if device is not None:
            tz = _device_zone(device)
        start_at, end_at = _day_bounds(day, tz)
        punches = list(
            TeacherBiometricPunch.objects.filter(
                teacher=teacher,
                punched_at__gte=start_at,
                punched_at__lt=end_at,
            ).select_related("device").order_by("punched_at", "id")
        )
        expected_start, expected_end = expected_teacher_window(teacher, day)
        first = punches[0].punched_at if punches else None
        last = punches[-1].punched_at if punches else None
        first_time = timezone.localtime(first, tz).time().replace(tzinfo=None) if first else None
        last_time = timezone.localtime(last, tz).time().replace(tzinfo=None) if last else None
        status = _derive_status(
            count=len(punches), first_time=first_time, last_time=last_time,
            expected_start=expected_start, expected_end=expected_end,
            late_grace=late_grace_minutes, early_grace=early_grace_minutes,
        )
        summary, created = BiometricDailySummary.objects.get_or_create(
            teacher=teacher,
            date=day,
            defaults={"derived_status": status},
        )
        prior_signature = (summary.first_punch_at, summary.last_punch_at, summary.punch_count, summary.derived_status)
        current_signature = (first, last, len(punches), status)
        summary.first_punch_at = first
        summary.last_punch_at = last
        summary.expected_start = expected_start
        summary.expected_end = expected_end
        summary.punch_count = len(punches)
        summary.source_devices_count = len({item.device_id for item in punches})
        summary.derived_status = status
        # New evidence re-opens only summaries that have not already changed the official record.
        if not created and prior_signature != current_signature and summary.review_status == "ignored":
            summary.review_status = "pending"
            summary.reviewed_by = None
            summary.reviewed_at = None
        summary.save()
        summaries.append(summary)
    return summaries


@transaction.atomic
def apply_daily_summary(summary: BiometricDailySummary, *, user, requested_status=""):
    summary = BiometricDailySummary.objects.select_for_update().select_related("teacher", "teacher__school").get(pk=summary.pk)
    status = (requested_status or summary.derived_status or "").strip()
    allowed = {"normal", "late", "early_departure", "absent"}
    if status not in allowed:
        raise ValidationError("هذه النتيجة تحتاج اختيارًا يدويًا: منتظم، متأخر، مغادرة مبكرة أو غائب.")
    existing = TeacherAbsence.objects.filter(teacher=summary.teacher, date=summary.date).first()
    if status == "normal":
        if existing is not None and existing != summary.applied_exception:
            raise ValidationError("يوجد استثناء دوام رسمي لهذا المعلم؛ راجعه يدويًا قبل اعتماد البصمة كمنتظم.")
        summary.applied_exception = None
    else:
        tz = timezone.get_current_timezone()
        device = BiometricDevice.objects.filter(teacher_identities__teacher=summary.teacher, teacher_identities__is_active=True).first()
        if device is not None:
            tz = _device_zone(device)
        arrival = timezone.localtime(summary.first_punch_at, tz).time().replace(tzinfo=None) if summary.first_punch_at else None
        departure = timezone.localtime(summary.last_punch_at, tz).time().replace(tzinfo=None) if summary.last_punch_at else None
        defaults = {
            "attendance_status": status,
            "arrival_time": arrival if status == "late" else None,
            "departure_time": departure if status == "early_departure" else None,
            "absence_type": "unexcused",
            "reason": "مقترح من تكامل جهاز البصمة ومراجع إداريًا",
            "is_approved": False,
            "payroll_approved": False,
            "deduction_amount": 0,
            "payroll_notes": "",
            "recorded_by": user,
        }
        exception, _created = TeacherAbsence.objects.update_or_create(
            teacher=summary.teacher, date=summary.date, defaults=defaults
        )
        sync_absence_coverages(exception, summary.teacher.school)
        summary.applied_exception = exception
    summary.review_status = "applied"
    summary.reviewed_by = user
    summary.reviewed_at = timezone.now()
    summary.save(update_fields=["review_status", "reviewed_by", "reviewed_at", "applied_exception", "updated_at"])
    return summary


@transaction.atomic
def ignore_daily_summary(summary: BiometricDailySummary, *, user, note=""):
    summary = BiometricDailySummary.objects.select_for_update().get(pk=summary.pk)
    summary.review_status = "ignored"
    summary.reviewed_by = user
    summary.reviewed_at = timezone.now()
    summary.note = (note or "")[:250]
    summary.save(update_fields=["review_status", "reviewed_by", "reviewed_at", "note", "updated_at"])
    return summary
