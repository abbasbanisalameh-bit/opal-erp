"""Single-source teacher work exceptions and class coverage services.

No daily ``present`` rows are generated.  An approved/recorded exception is
applied only to the timetable entries that its status and time affect.
"""
from __future__ import annotations

from django.db import transaction

from .models import ClassCoverage, TeacherAbsence, TimetableEntry

FULL_DAY_UNAVAILABLE = {"absent", "approved_excuse", "official_mission"}


def absence_affects_entry(absence, entry) -> bool:
    if not absence or absence.attendance_status == "present":
        return False
    status = absence.attendance_status
    if status in FULL_DAY_UNAVAILABLE:
        return True
    start = entry.time_slot.start_time
    if status == "late":
        return bool(absence.arrival_time and start < absence.arrival_time)
    if status == "early_departure":
        return bool(absence.departure_time and start >= absence.departure_time)
    return False


def public_teacher_state(absence, coverage=None) -> dict:
    """Privacy-safe state for schedule/guardian screens."""
    if coverage and coverage.status == "assigned" and coverage.substitute_teacher_id:
        return {
            "code": "substitute",
            "label": f"المعلم البديل: {coverage.substitute_teacher}",
            "substitute": coverage.substitute_teacher,
        }
    if not absence:
        return {"code": "available", "label": "المعلم متاح", "substitute": None}
    if absence.attendance_status == "absent":
        return {"code": "absent", "label": "معلم غائب", "substitute": None}
    return {"code": "unavailable", "label": "المعلم غير متاح", "substitute": None}


def teacher_exception(teacher_id, date):
    if not teacher_id:
        return None
    return TeacherAbsence.objects.filter(teacher_id=teacher_id, date=date).first()


def teacher_unavailable_for_entry(*, teacher_id, date, entry) -> bool:
    return absence_affects_entry(teacher_exception(teacher_id, date), entry)


def affected_entries_for_absence(absence, school=None):
    # DAY_CODES is deliberately local to avoid an import cycle with live_services.
    codes = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"}
    queryset = TimetableEntry.objects.filter(
        teacher=absence.teacher,
        day=codes[absence.date.weekday()],
        academic_year__is_current=True,
        is_active=True,
    ).select_related("time_slot", "academic_year")
    if school is not None:
        queryset = queryset.filter(academic_year__school=school)
    return [entry for entry in queryset if absence_affects_entry(absence, entry)]


@transaction.atomic
def sync_absence_coverages(absence, school=None):
    """Synchronise only pending coverage needs; preserve assigned audit records."""
    affected = affected_entries_for_absence(absence, school)
    affected_ids = {entry.pk for entry in affected}
    for entry in affected:
        coverage, created = ClassCoverage.objects.get_or_create(entry=entry, date=absence.date)
        if not created and coverage.status == "cancelled":
            coverage.status = "needed"
            coverage.save(update_fields=["status"])

    existing = ClassCoverage.objects.filter(
        entry__teacher=absence.teacher,
        date=absence.date,
        entry__academic_year__is_current=True,
    )
    if school is not None:
        existing = existing.filter(entry__academic_year__school=school)
    for coverage in existing.exclude(entry_id__in=affected_ids):
        if coverage.status == "needed":
            coverage.status = "cancelled"
            coverage.save(update_fields=["status"])
    return affected


def decorate_entries_with_daily_status(entries, date):
    """Attach privacy-safe status to in-memory timetable entries in three queries."""
    items = list(entries)
    teacher_ids = {item.teacher_id for item in items if item.teacher_id}
    entry_ids = {item.pk for item in items if item.pk}
    absences = {
        row.teacher_id: row
        for row in TeacherAbsence.objects.filter(teacher_id__in=teacher_ids, date=date)
    }
    coverages = {
        row.entry_id: row
        for row in ClassCoverage.objects.filter(entry_id__in=entry_ids, date=date)
        .select_related("substitute_teacher")
    }
    for item in items:
        absence = absences.get(item.teacher_id)
        if absence and not absence_affects_entry(absence, item):
            absence = None
        coverage = coverages.get(item.pk)
        item.work_exception = absence
        item.coverage = coverage
        item.teacher_state = public_teacher_state(absence, coverage)
        item.teacher_state_code = item.teacher_state["code"]
        item.teacher_state_label = item.teacher_state["label"]
        item.substitute_teacher = item.teacher_state["substitute"]
    return items


def decorate_weekly_entries_with_current_status(entries, *, date, current_day_code):
    """Decorate only today's row in a reusable weekly timetable matrix.

    A weekly matrix represents weekdays, not concrete calendar dates.  Applying
    today's exception to every row makes one absence appear on the whole week.
    Non-today rows therefore receive the neutral public state, while today's
    entries retain the official exception/coverage lookup.
    """
    items = list(entries)
    today_items = [item for item in items if item.day == current_day_code]
    decorate_entries_with_daily_status(today_items, date)
    neutral_state = public_teacher_state(None, None)
    for item in items:
        if item.day == current_day_code:
            continue
        item.work_exception = None
        item.coverage = None
        item.teacher_state = neutral_state.copy()
        item.teacher_state_code = item.teacher_state["code"]
        item.teacher_state_label = item.teacher_state["label"]
        item.substitute_teacher = None
    return items

