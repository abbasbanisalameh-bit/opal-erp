"""Live timetable state derived from official schedule and work exceptions."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from django.utils import timezone

from academics.models import Enrollment, Section
from teachers.models import Teacher

from .attendance_services import decorate_entries_with_daily_status
from .models import SchoolDayEvent, SchoolScheduleSettings, TimeSlot, TimetableEntry

DAY_CODES = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"}


def _now_parts(now=None):
    now = timezone.localtime(now or timezone.now())
    return now, DAY_CODES[now.weekday()], now.time().replace(tzinfo=None)


def _seconds_until(now, target_time):
    target = timezone.make_aware(datetime.combine(now.date(), target_time), timezone.get_current_timezone())
    return max(int((target - now).total_seconds()), 0)


def _status_from_rows(*, settings, now, current_time, rows, guardian=False):
    if not rows:
        return {
            "state": "no_schedule",
            "current": None,
            "next": None,
            "message": "لا يوجد دوام مقرر اليوم",
            "seconds_remaining": None,
            "ends_soon": False,
        }

    current_candidates = [row for row in rows if row["start"] <= current_time < row["end"]]
    # Explicit school events (especially staggered breaks) override a class
    # slot if configuration times overlap.
    current = min(
        current_candidates,
        key=lambda row: (row.get("kind") == "class", row["start"], row["end"], row["name"]),
        default=None,
    )
    following = next((row for row in rows if row["start"] > current_time), None)
    status = {"state": "active" if current else "between", "current": current, "next": following, "message": ""}
    if current:
        status["seconds_remaining"] = _seconds_until(now, current["end"])
        status["ends_soon"] = status["seconds_remaining"] <= settings.alert_minutes_before_end * 60
        status["message"] = f"الحدث الجاري: {current['name']}"
    elif following:
        before_first_event = current_time < rows[0]["start"]
        status["state"] = "not_started" if before_first_event else "between"
        status["seconds_remaining"] = _seconds_until(now, following["start"])
        status["ends_soon"] = False
        status["message"] = (
            f"لم يبدأ الدوام — التالي: {following['name']}"
            if before_first_event else f"بين حدثين — التالي: {following['name']}"
        )
    else:
        status.update({"state": "finished", "message": "خارج وقت الدوام", "seconds_remaining": None, "ends_soon": False})
    return status


def _section_live_statuses(school, sections, now):
    """Calculate all section states with bounded queries, including staggered breaks."""
    now, day, current_time = _now_parts(now)
    settings = SchoolScheduleSettings.objects.filter(school=school).first() or SchoolScheduleSettings(school=school)
    if day in settings.weekend_day_codes:
        return {
            section.pk: {
                "state": "weekend",
                "message": "عطلة نهاية أسبوع سعيدة",
                "current": None,
                "next": None,
                "seconds_remaining": None,
            }
            for section in sections
        }

    global_events = []
    events_by_section = defaultdict(list)
    events = SchoolDayEvent.objects.filter(
        school=school, is_active=True,
        start_time__isnull=False, end_time__isnull=False,
    ).prefetch_related("sections")
    for event in events:
        if day not in event.day_codes:
            continue
        row = {"name": event.name, "start": event.start_time, "end": event.end_time, "kind": event.event_type}
        linked_ids = [section.pk for section in event.sections.all()]
        if linked_ids:
            for section_id in linked_ids:
                events_by_section[section_id].append(row)
        else:
            global_events.append(row)

    slots_by_section = defaultdict(list)
    entries = TimetableEntry.objects.filter(
        academic_year__school=school, academic_year__is_current=True,
        day=day, is_active=True, section_id__in=[section.pk for section in sections],
        time_slot__is_active=True,
    ).select_related("time_slot")
    seen_slots = set()
    for entry in entries:
        key = (entry.section_id, entry.time_slot_id)
        if key in seen_slots:
            continue
        seen_slots.add(key)
        slots_by_section[entry.section_id].append({
            "name": entry.time_slot.name.replace(" — توقيت ذكي", ""),
            "start": entry.time_slot.start_time,
            "end": entry.time_slot.end_time,
            "kind": "class",
        })
    statuses = {}
    for section in sections:
        rows = list(global_events) + list(events_by_section.get(section.pk, ()))
        # A grade/section live state must be derived from its actual scheduled
        # entries.  Generic time slots would falsely report a class for a
        # section that has no lesson scheduled today.
        rows.extend(slots_by_section.get(section.pk, ()))
        unique = {(row["name"], row["start"], row["end"], row["kind"]): row for row in rows}
        ordered = sorted(unique.values(), key=lambda row: (row["start"], row["end"], row["name"]))
        statuses[section.pk] = _status_from_rows(
            settings=settings, now=now, current_time=current_time, rows=ordered,
        )
    return statuses


def _event_rows(school, day, section_id=None):
    rows = []
    events = SchoolDayEvent.objects.filter(
        school=school, is_active=True,
        start_time__isnull=False, end_time__isnull=False,
    ).prefetch_related("sections")
    for event in events:
        if day not in event.day_codes:
            continue
        linked_sections = {section.pk for section in event.sections.all()}
        if linked_sections and section_id is not None and section_id not in linked_sections:
            continue
        rows.append({"name": event.name, "start": event.start_time, "end": event.end_time, "kind": event.event_type})
    entry_slots_qs = TimeSlot.objects.filter(
        entries__academic_year__school=school,
        entries__academic_year__is_current=True,
        entries__day=day,
        entries__is_active=True,
        is_active=True,
    )
    if section_id:
        entry_slots_qs = entry_slots_qs.filter(entries__section_id=section_id)
    entry_slots = list(entry_slots_qs.distinct())
    # Live state is derived only from official timetable entries. Generic
    # time-slot definitions must not invent a school day for a section or a
    # school that has no scheduled lessons today.
    for slot in entry_slots:
        rows.append({"name": slot.name.replace(" — توقيت ذكي", ""), "start": slot.start_time, "end": slot.end_time, "kind": "class"})
    unique = {(row["name"], row["start"], row["end"], row["kind"]): row for row in rows}
    return sorted(unique.values(), key=lambda row: (row["start"], row["end"], row["name"]))


def school_live_status(school, now=None, *, guardian=False, section_id=None):
    now, day, current_time = _now_parts(now)
    settings = SchoolScheduleSettings.objects.filter(school=school).first() or SchoolScheduleSettings(school=school)
    if day in settings.weekend_day_codes:
        return {
            "state": "weekend",
            "message": "عطلة نهاية أسبوع سعيدة. اعتنوا بأبنائنا جيدًا." if guardian else "عطلة نهاية أسبوع سعيدة",
            "current": None, "next": None, "seconds_remaining": None,
        }
    rows = _event_rows(school, day, section_id=section_id)
    return _status_from_rows(
        settings=settings, now=now, current_time=current_time, rows=rows, guardian=guardian,
    )


def teacher_live_status(teacher, now=None):
    now, day, current_time = _now_parts(now)
    base = school_live_status(teacher.school, now)
    if base["state"] == "weekend":
        return base
    entries = list(TimetableEntry.objects.filter(
        teacher=teacher, day=day, is_active=True,
        academic_year__school=teacher.school, academic_year__is_current=True,
    ).select_related("section__grade", "subject", "time_slot").order_by("time_slot__start_time"))
    decorate_entries_with_daily_status(entries, now.date())
    current = next((row for row in entries if row.time_slot.start_time <= current_time < row.time_slot.end_time), None)
    following = next((row for row in entries if row.time_slot.start_time > current_time), None)
    return {
        **base,
        "current_class": current,
        "next_class": following,
        "teacher_message": f"الحصة الحالية: {current.section}" if current else "الحصة الحالية: فراغ",
        "teacher_next_message": f"الحصة التالية: {following.section}" if following else "لا توجد حصة تالية",
    }


def student_live_status(student, now=None):
    enrollment = Enrollment.objects.filter(student=student, status="active").select_related(
        "academic_year__school", "section__grade"
    ).order_by("-academic_year__start_date").first()
    if not enrollment or not enrollment.section_id:
        return {"state": "unavailable", "message": "لا يوجد جدول دراسي فعال"}
    now, day, current_time = _now_parts(now)
    base = school_live_status(
        enrollment.academic_year.school, now, guardian=True, section_id=enrollment.section_id,
    )
    if base["state"] == "weekend":
        return base
    entries = list(TimetableEntry.objects.filter(
        section=enrollment.section, academic_year=enrollment.academic_year,
        day=day, is_active=True,
    ).select_related("subject", "teacher", "time_slot").order_by("time_slot__start_time"))
    decorate_entries_with_daily_status(entries, now.date())
    current = next((row for row in entries if row.time_slot.start_time <= current_time < row.time_slot.end_time), None)
    following = next((row for row in entries if row.time_slot.start_time > current_time), None)
    if not current and not following and entries:
        base.update({"state": "finished", "message": "انتهى دوام الطالب"})
    return {**base, "current_class": current, "next_class": following}


def _management_base_status(school, section_statuses, now):
    """Build the management headline from already-calculated section states."""
    if not section_statuses:
        return school_live_status(school, now)

    statuses = list(section_statuses.values())
    transition_seconds = [
        status.get("seconds_remaining")
        for status in statuses
        if status.get("seconds_remaining") is not None
    ]
    if all(status.get("state") == "weekend" for status in statuses):
        return {
            "state": "weekend",
            "message": "عطلة نهاية أسبوع سعيدة",
            "current": None,
            "next": None,
            "seconds_remaining": None,
        }
    if all(status.get("state") == "no_schedule" for status in statuses):
        return {
            "state": "no_schedule",
            "message": "لا يوجد دوام مقرر اليوم",
            "current": None,
            "next": None,
            "seconds_remaining": None,
        }

    current_rows = [status["current"] for status in statuses if status.get("current")]
    next_rows = [status["next"] for status in statuses if status.get("next")]
    current = min(
        current_rows,
        key=lambda row: (row.get("kind") == "class", row["start"], row["end"], row["name"]),
        default=None,
    )
    following = min(next_rows, key=lambda row: (row["start"], row["end"], row["name"]), default=None)
    if current:
        return {
            "state": "active",
            "message": f"الحدث الجاري: {current['name']}",
            "current": current,
            "next": following,
            "seconds_remaining": min(transition_seconds) if transition_seconds else None,
            "ends_soon": any(status.get("ends_soon") for status in statuses),
        }
    if following:
        state_values = {status.get("state") for status in statuses}
        not_started = state_values <= {"not_started", "no_schedule"}
        return {
            "state": "not_started" if not_started else "between",
            "message": (
                f"لم يبدأ الدوام — التالي: {following['name']}"
                if not_started else f"بين حدثين — التالي: {following['name']}"
            ),
            "current": None,
            "next": following,
            "seconds_remaining": min(transition_seconds) if transition_seconds else None,
            "ends_soon": False,
        }
    return {
        "state": "finished",
        "message": "خارج وقت الدوام",
        "current": None,
        "next": None,
        "seconds_remaining": None,
    }


def management_live_status(school, now=None):
    """Return the director's live operational picture in bounded queries.

    The result distinguishes teachers who are effectively teaching now from
    unavailable original teachers, exposes free teachers only during the school
    operating window, and keeps a current event row for every active grade.
    """
    now, day, current_time = _now_parts(now)

    sections = list(Section.objects.filter(
        academic_year__school=school, academic_year__is_current=True, is_active=True,
    ).select_related("grade").order_by("grade__order", "grade__name", "name"))
    section_statuses = _section_live_statuses(school, sections, now)
    base = _management_base_status(school, section_statuses, now)

    current_entries = list(TimetableEntry.objects.filter(
        academic_year__school=school, academic_year__is_current=True,
        day=day, is_active=True, time_slot__is_active=True,
        time_slot__start_time__lte=current_time,
        time_slot__end_time__gt=current_time,
    ).select_related("teacher", "section__grade", "subject", "time_slot"))
    decorate_entries_with_daily_status(current_entries, now.date())

    visible_entries = []
    busy_rows = []
    busy_ids = set()
    for entry in current_entries:
        section_current = section_statuses.get(entry.section_id, {}).get("current")
        if section_current and section_current.get("kind") != "class":
            # A configured break/event is the official current state for this
            # section, even if a time-slot range overlaps it accidentally.
            continue
        visible_entries.append(entry)
        effective_teacher = None
        is_substitute = False
        if entry.teacher_state_code == "substitute" and entry.substitute_teacher:
            effective_teacher = entry.substitute_teacher
            is_substitute = True
        elif entry.teacher_state_code == "available" and entry.teacher_id:
            effective_teacher = entry.teacher

        # An absent/unavailable original teacher is not a busy teacher.  The
        # substitute, when assigned, is the effective busy teacher instead.
        if effective_teacher:
            busy_ids.add(effective_teacher.pk)
            busy_rows.append({
                "teacher": effective_teacher,
                "entry": entry,
                "is_substitute": is_substitute,
                "original_teacher": entry.teacher if is_substitute else None,
            })

    all_teachers = list(Teacher.objects.filter(school=school, is_active=True).order_by("full_name"))
    unavailable_ids = set()
    from .models import TeacherAbsence
    for absence in TeacherAbsence.objects.filter(
        teacher__school=school, date=now.date(),
    ).select_related("teacher"):
        if absence.attendance_status in {"absent", "approved_excuse", "official_mission"}:
            unavailable_ids.add(absence.teacher_id)
        elif absence.attendance_status == "late" and absence.arrival_time and current_time < absence.arrival_time:
            unavailable_ids.add(absence.teacher_id)
        elif absence.attendance_status == "early_departure" and absence.departure_time and current_time >= absence.departure_time:
            unavailable_ids.add(absence.teacher_id)

    teacher_state_active = base.get("state") in {"active", "between"}
    free_teachers = (
        [teacher for teacher in all_teachers if teacher.pk not in busy_ids | unavailable_ids]
        if teacher_state_active else []
    )

    # Keep both the legacy compact grade summary and the canonical horizontal
    # grade/section/event matrix.  Both are derived from the same bounded query
    # result, so the dashboard gains detail without extra database work.
    by_grade = defaultdict(list)
    entries_by_section = {entry.section_id: entry for entry in visible_entries}
    for section in sections:
        entry = entries_by_section.get(section.pk)
        section_status = section_statuses[section.pk]
        current_event = section_status.get("current")
        state_code = section_status.get("state", "finished")
        meta = ""
        subject_color = ""

        if current_event and current_event.get("kind") != "class":
            label = current_event["name"]
            state_code = current_event.get("kind") or "event"
            meta = f"{current_event['start'].strftime('%H:%M')}–{current_event['end'].strftime('%H:%M')}"
        elif entry:
            label = entry.subject.name
            subject_color = entry.subject.color or "#64748B"
            state_code = "class"
            meta = entry.time_slot.name.replace(" — توقيت ذكي", "")
            if entry.teacher_state_code == "substitute":
                state_code = "substitute"
                meta += f" — {entry.teacher_state_label}"
            elif entry.teacher_state_code != "available":
                state_code = "teacher-unavailable"
                meta += f" — {entry.teacher_state_label}"
        elif current_event:
            label = current_event["name"]
            state_code = current_event.get("kind") or "class"
        elif section_status.get("next"):
            label = "لم يبدأ الدوام" if section_status.get("state") == "not_started" else "بين حدثين"
            following = section_status["next"]
            meta = f"التالي: {following['name']} — {following['start'].strftime('%H:%M')}"
        else:
            label = section_status.get("message", "خارج وقت الدوام")

        short_name = section.name
        if short_name.startswith("شعبة "):
            short_name = short_name[len("شعبة "):].strip()
        by_grade[section.grade].append({
            "section": section,
            "short_name": short_name or section.name,
            "label": label,
            "meta": meta,
            "state_code": state_code,
            "subject_color": subject_color,
        })

    grade_columns = [
        {
            "grade": grade,
            "sections": values,
            "section_count": len(values),
        }
        for grade, values in by_grade.items()
    ]

    grade_rows = []
    for grade, values in by_grade.items():
        states = defaultdict(list)
        for item in values:
            states[item["label"]].append(item["section"].name)
        grade_rows.append({
            "grade": grade,
            "is_multiple": len(states) > 1,
            "states": [
                {"label": label, "sections": "، ".join(names)}
                for label, names in states.items()
            ],
        })

    active_section_labels = {
        status["current"]["name"] if status.get("current") else status.get("message", "")
        for status in section_statuses.values()
    }
    if len(active_section_labels) > 1:
        base["message"] = "أحداث متعددة حسب الصفوف والشعب"

    return {
        **base,
        "current_entries": visible_entries,
        "busy_rows": busy_rows,
        "busy_teachers": len(busy_ids) if teacher_state_active else 0,
        "busy_teacher_ids": busy_ids,
        "unavailable_teacher_ids": unavailable_ids,
        "free_teachers": free_teachers,
        "free_teachers_count": len(free_teachers),
        "teacher_state_active": teacher_state_active,
        "teacher_state_message": (
            "الحالة محسوبة من الحصص الجارية واستثناءات دوام اليوم."
            if teacher_state_active
            else (
                "لم يبدأ وقت التشغيل المدرسي بعد."
                if base.get("state") == "not_started"
                else "لا تُحسب حالة إشغال المعلمين خارج وقت الدوام أو في يوم بلا جدول."
            )
        ),
        "grade_rows": grade_rows,
        "grade_columns": grade_columns,
        "day_code": day,
        "current_time": current_time,
    }
