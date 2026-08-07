"""Canonical timetable workflow for OPAL ERP.

The official timetable, smart builder, live state, breaks and coverage all use
existing models and this one orchestration layer.  Display filters never select
another school or academic year.
"""
from __future__ import annotations

from collections import defaultdict

from django.utils import timezone

from academics.models import Subject
from core.models import AcademicYear
from teachers.models import Teacher
from admissions.services import active_school

from .attendance_services import (
    decorate_entries_with_daily_status,
    decorate_weekly_entries_with_current_status,
    sync_absence_coverages,
    teacher_unavailable_for_entry,
)
from .live_services import DAY_CODES, management_live_status
from .models import ClassCoverage, SchoolDayEvent, SchoolScheduleSettings, TimeSlot, TimetableEntry
from .services import build_smart_timetable

WORKING_DAY_CODES = ("sunday", "monday", "tuesday", "wednesday", "thursday")


def _clean_period_name(name):
    return (name or "").replace(" — توقيت ذكي", "").strip()


def _slot_time_label(slot):
    return f"{slot.start_time.strftime('%H:%M')}–{slot.end_time.strftime('%H:%M')}" if slot else ""


def _entry_matrix_sort_key(item):
    return (
        getattr(getattr(item.section, "grade", None), "order", 0) or 0,
        getattr(item.section, "name", "") or "",
        getattr(item.subject, "name", "") or "",
        getattr(item.teacher, "full_name", "") or "",
        item.pk or 0,
    )


def _period_headers(items, explicit_periods=None):
    if explicit_periods is not None:
        return [dict(period) for period in explicit_periods]

    grouped = defaultdict(list)
    for item in items:
        grouped[item.time_slot.order].append(item)
    if not grouped:
        for slot in TimeSlot.objects.filter(is_active=True, generated_for_smart_schedule=False).order_by("order", "start_time", "pk"):
            grouped[slot.order].append(slot)

    headers = []
    for order in sorted(grouped):
        values = grouped[order]
        first_slot = values[0].time_slot if hasattr(values[0], "time_slot") else values[0]
        ranges = defaultdict(set)
        for value in values:
            slot = value.time_slot if hasattr(value, "time_slot") else value
            section = getattr(value, "section", None)
            ranges[_slot_time_label(slot)].add(str(section) if section else "")
        time_labels = []
        for label, sections in sorted(ranges.items()):
            clean_sections = sorted(item for item in sections if item)
            time_labels.append({
                "label": label,
                "sections_label": "، ".join(clean_sections) if len(ranges) > 1 and clean_sections else "",
            })
        headers.append({
            "order": order,
            "name": _clean_period_name(first_slot.name) or f"الحصة {order}",
            "time_label": time_labels[0]["label"] if len(time_labels) == 1 else "",
            "time_labels": time_labels,
        })
    return headers


def _breaks_by_cell(*, school, items, periods, day_codes):
    result = defaultdict(list)
    if not school or not periods:
        return result
    visible_section_ids = {item.section_id for item in items if getattr(item, "section_id", None)}
    for event in SchoolDayEvent.objects.filter(
        school=school,
        event_type="break",
        is_active=True,
        start_time__isnull=False,
        end_time__isnull=False,
    ).prefetch_related("sections"):
        linked_sections = list(event.sections.all())
        linked_ids = {section.pk for section in linked_sections}
        if linked_ids and visible_section_ids and linked_ids.isdisjoint(visible_section_ids):
            continue
        relevant_items = [
            item for item in items
            if not linked_ids or getattr(item, "section_id", None) in linked_ids
        ]
        entries_by_order = defaultdict(list)
        for item in relevant_items:
            entries_by_order[item.time_slot.order].append(item)
        end_by_order = {
            order: max(item.time_slot.end_time for item in values)
            for order, values in entries_by_order.items()
        }
        for day in day_codes:
            if day not in event.day_codes:
                continue
            eligible = [
                period["order"] for period in periods
                if end_by_order.get(period["order"]) and end_by_order[period["order"]] <= event.start_time
            ]
            order = max(eligible) if eligible else periods[0]["order"]
            result[(day, order)].append({
                "name": event.name,
                "time_label": f"{event.start_time.strftime('%H:%M')}–{event.end_time.strftime('%H:%M')}",
                "sections_label": "، ".join(str(section) for section in linked_sections),
            })
    return result


def build_horizontal_schedule_matrix(entries, *, selected_day="", periods=None, now=None, school=None, show_free=False, reference_entries=None):
    """Return one row per day and one column per lesson order.

    Clock ranges are rendered in column headers only.  Breaks are derived from
    ``SchoolDayEvent`` and teacher free periods are derived from the unfiltered
    timetable; neither creates database rows.
    """
    items = list(entries)
    reference_items = list(reference_entries) if reference_entries is not None else items
    local_now = now or timezone.localtime()
    local_now = timezone.make_aware(local_now) if timezone.is_naive(local_now) else timezone.localtime(local_now)
    current_day_code = DAY_CODES[local_now.weekday()]
    current_time = local_now.time().replace(tzinfo=None)
    decorate_weekly_entries_with_current_status(
        items, date=local_now.date(), current_day_code=current_day_code,
    )

    for item in items:
        item.is_current_lesson = bool(
            item.day == current_day_code and item.is_active
            and item.time_slot.start_time <= current_time < item.time_slot.end_time
        )
        item.subject_colour = getattr(item.subject, "color", "") or "#2563EB"

    period_headers = _period_headers(reference_items, periods)
    labels = dict(TimetableEntry.DAYS)
    if selected_day and selected_day in labels:
        day_codes = [selected_day]
    else:
        day_codes = list(WORKING_DAY_CODES)
        for code, _label in TimetableEntry.DAYS:
            if code not in day_codes and any(item.day == code for item in items):
                day_codes.append(code)

    grouped = defaultdict(list)
    for item in items:
        grouped[(item.day, item.time_slot.order)].append(item)
    breaks = _breaks_by_cell(school=school, items=reference_items, periods=period_headers, day_codes=day_codes)
    occupied = {(item.day, item.time_slot.order) for item in reference_items}

    rows = []
    for day_code in day_codes:
        cells = []
        for period in period_headers:
            cell_items = sorted(grouped.get((day_code, period["order"]), []), key=_entry_matrix_sort_key)
            cells.append({
                "order": period["order"],
                "entries": cell_items,
                "break_events": breaks.get((day_code, period["order"]), []),
                "is_current": any(item.is_current_lesson for item in cell_items),
                "is_free": bool(show_free and (day_code, period["order"]) not in occupied),
            })
        rows.append({
            "code": day_code,
            "label": labels.get(day_code, day_code),
            "is_today": day_code == current_day_code,
            "cells": cells,
        })
    return {
        "periods": period_headers,
        "rows": rows,
        "has_entries": bool(items),
        "entry_count": len(items),
        "current_day_code": current_day_code,
        "has_current_lesson": any(item.is_current_lesson for item in items),
    }


def build_smart_plan_matrix(result):
    if not result:
        return {"periods": [], "rows": [], "has_entries": False}
    plan = list(result.get("plan", []))
    pseudo_entries = []
    for row in plan:
        # Reuse the proposal's real slot/section data only to build accurate headers.
        class ProposalEntry:
            pass
        item = ProposalEntry()
        item.time_slot = row["base_slot"]
        item.section = row["assignment"].section
        pseudo_entries.append(item)
    periods = _period_headers(pseudo_entries)
    grouped = defaultdict(list)
    for item in plan:
        grouped[(item["day"], item["base_slot"].order)].append(item)
    rows = []
    for day_code, day_label in result.get("working_day_options", []):
        cells = []
        for period in periods:
            values = sorted(grouped.get((day_code, period["order"]), []), key=lambda item: (
                getattr(item["assignment"].section.grade, "order", 0),
                item["assignment"].section.name,
                item["assignment"].subject.name,
            ))
            cells.append({"order": period["order"], "entries": values})
        rows.append({"code": day_code, "label": day_label, "cells": cells})
    return {"periods": periods, "rows": rows, "has_entries": bool(plan)}


def current_school_year(school):
    return AcademicYear.objects.filter(school=school, is_current=True).order_by("-start_date").first()


def build_timetable_dashboard_context(request, *, builder_state=None):
    school = active_school()
    year = current_school_year(school)
    filters = {
        "teacher": request.GET.get("teacher", ""),
        "day": request.GET.get("day", ""),
        "period": request.GET.get("period", ""),
        "subject": request.GET.get("subject", ""),
    }
    base_entries = TimetableEntry.objects.none()
    if year:
        base_entries = TimetableEntry.objects.filter(
            academic_year=year, is_active=True,
        ).select_related("academic_year", "section__grade", "subject__grade", "teacher", "time_slot")
    entries = base_entries
    if filters["teacher"]:
        entries = entries.filter(teacher_id=filters["teacher"])
    if filters["day"]:
        entries = entries.filter(day=filters["day"])
    if filters["period"]:
        entries = entries.filter(time_slot__order=filters["period"])
    if filters["subject"]:
        entries = entries.filter(subject_id=filters["subject"])

    reference_items = list(base_entries.filter(teacher_id=filters["teacher"])) if filters["teacher"] else list(base_entries)
    matrix_items = list(entries)
    schedule_matrix = build_horizontal_schedule_matrix(
        matrix_items,
        selected_day=filters["day"],
        school=school,
        show_free=bool(filters["teacher"]),
        reference_entries=reference_items,
    )
    context = {
        "entries": matrix_items,
        "schedule_matrix": schedule_matrix,
        "school": school,
        "current_year": year,
        "teachers": Teacher.objects.filter(school=school, is_active=True).order_by("full_name"),
        "subjects": Subject.objects.filter(academic_year=year, is_active=True).select_related("grade").order_by("grade__order", "name") if year else Subject.objects.none(),
        "periods": sorted({item.time_slot.order for item in reference_items}, key=int) if year else [],
        "days": TimetableEntry.DAYS,
        "filters": filters,
        "live_status": management_live_status(school),
        "coverage_needed": ClassCoverage.objects.filter(
            date=timezone.localdate(), status="needed",
            entry__academic_year=year,
        ).select_related("entry__section__grade", "entry__subject", "entry__teacher", "entry__time_slot") if year else ClassCoverage.objects.none(),
    }
    context.update(builder_state or build_smart_builder_state(request, execute=False))
    return context


def build_smart_builder_state(request, *, execute=True):
    school = active_school()
    years = AcademicYear.objects.filter(school=school, is_closed=False).order_by("-is_current", "-start_date")
    year_id = request.POST.get("builder_year") or request.GET.get("builder_year")
    year = years.filter(pk=year_id).first() if year_id else years.first()
    result = None
    action = request.POST.get("action", "") if request.method == "POST" else ""
    apply = action == "builder_apply"
    preview = action in {"builder_preview", "builder_apply"}
    variant = request.POST.get("variant") or request.GET.get("variant") or "balanced"
    if variant not in {"balanced", "compact", "spread"}:
        variant = "balanced"
    overrides = {}
    if request.method == "POST":
        for key, value in request.POST.items():
            if key.startswith("day__"):
                overrides.setdefault(key[5:], {})["day"] = value
            elif key.startswith("slot__"):
                overrides.setdefault(key[6:], {})["slot"] = value
    if execute and preview and year:
        result = build_smart_timetable(
            academic_year=year,
            apply=apply,
            replace_generated=request.POST.get("replace_generated") == "1",
            variant=variant,
            expected_fingerprint=request.POST.get("source_fingerprint", "") if apply else "",
            overrides=overrides,
        )
        result["plan_matrix"] = build_smart_plan_matrix(result)
    return {
        "builder_years": years,
        "builder_year": year,
        "builder_result": result,
        "builder_apply": apply,
        "builder_variant": variant,
    }


def build_schedule_settings_context(*, school, settings_form, event_form):
    return {
        "settings_form": settings_form,
        "event_form": event_form,
        "events": SchoolDayEvent.objects.filter(school=school).prefetch_related("sections"),
    }


def create_absence_coverages(absence, school):
    return sync_absence_coverages(absence, school)


def upcoming_coverages_queryset(school=None):
    queryset = ClassCoverage.objects.filter(date__gte=timezone.localdate()).select_related(
        "entry__teacher", "entry__section__grade", "entry__subject", "entry__time_slot", "substitute_teacher"
    ).order_by("date", "entry__time_slot__order")
    if school is not None:
        queryset = queryset.filter(entry__academic_year__school=school)
    return queryset


def substitute_teacher_is_unavailable(*, coverage, substitute):
    entry = coverage.entry
    busy = TimetableEntry.objects.filter(
        teacher=substitute,
        academic_year=entry.academic_year,
        day=entry.day,
        is_active=True,
        time_slot__start_time__lt=entry.time_slot.end_time,
        time_slot__end_time__gt=entry.time_slot.start_time,
    ).exists()
    unavailable = teacher_unavailable_for_entry(
        teacher_id=substitute.pk, date=coverage.date, entry=entry,
    )
    return busy or unavailable


def build_print_context(entries, title, school=None):
    items = list(entries)
    return {
        "title": title,
        "schedule_matrix": build_horizontal_schedule_matrix(items, school=school),
    }


def section_schedule_queryset(section):
    return TimetableEntry.objects.filter(section=section, is_active=True).select_related(
        "academic_year__school", "section__grade", "subject", "teacher", "time_slot"
    )


def teacher_schedule_queryset(teacher):
    return TimetableEntry.objects.filter(
        teacher=teacher, academic_year__is_current=True, is_active=True,
    ).select_related("academic_year__school", "section__grade", "subject", "time_slot")


def active_time_slots_queryset():
    return TimeSlot.objects.all().order_by("generated_for_smart_schedule", "order", "start_time")


def school_schedule_settings(school):
    return SchoolScheduleSettings.objects.get_or_create(school=school)[0]
