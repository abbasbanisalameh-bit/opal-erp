"""Safe smart timetable proposal engine built on OPAL's existing models.

No parallel timetable or draft model is introduced.  The engine reads the
canonical annual subject plan, teacher assignments, teacher workload settings, existing
time slots and existing day-event records.  A proposal is recomputed and
fingerprinted before atomic approval.
"""
from collections import Counter, defaultdict
from datetime import time
import hashlib
import json
import math

from django.core.exceptions import ValidationError
from django.db import transaction

from academics.models import Section, Subject
from teachers.models import TeacherAssignment
from teachers.workload import workload_by_teacher

from .models import SchoolDayEvent, SchoolScheduleSettings, TimeSlot, TimetableEntry


CANONICAL_WORKING_DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday"]
DAY_LABELS = dict(TimetableEntry.DAYS)
BREAK_MARGIN_MINUTES = 120


def _minutes(value):
    return value.hour * 60 + value.minute


def _clock(value):
    value = int(value) % (24 * 60)
    return time(value // 60, value % 60)


def _overlap(start_a, end_a, start_b, end_b):
    return start_a < end_b and end_a > start_b


def _source_fingerprint(*, academic_year, assignments, plan_subjects, slots, breaks, settings, existing):
    payload = {
        "year": academic_year.pk,
        "weekend": sorted(settings.weekend_day_codes),
        "assignments": [
            [
                item.pk,
                item.teacher_id,
                item.section_id,
                item.subject_id,
                item.is_active,
            ]
            for item in assignments
        ],
        "subjects": [
            [item.pk, item.grade_id, item.weekly_periods, item.is_required, item.color, item.is_active]
            for item in plan_subjects
        ],
        "teachers": sorted(
            [
                item.teacher_id,
                item.teacher.weekly_teaching_load,
                item.teacher.free_period_policy,
                item.teacher.daily_free_periods,
                item.teacher.weekly_free_periods,
            ]
            for item in assignments
        ),
        "slots": [
            [item.pk, item.name, str(item.start_time), str(item.end_time), item.order, item.is_active]
            for item in slots
        ],
        "breaks": [
            [
                item.pk,
                item.name,
                item.placement_mode,
                item.duration_minutes,
                str(item.start_time),
                str(item.end_time),
                sorted(item.day_codes),
                sorted(section.pk for section in item.sections.all()),
                item.is_active,
            ]
            for item in breaks
        ],
        "official_entries": [
            [
                item.pk, item.section_id, item.subject_id, item.teacher_id, item.day,
                item.time_slot_id, str(item.time_slot.start_time), str(item.time_slot.end_time),
                item.room, item.generated_automatically, item.is_active,
            ]
            for item in existing
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _break_specs(*, school, sections, slots, blockers):
    breaks = list(
        SchoolDayEvent.objects.filter(
            school=school,
            event_type="break",
            is_active=True,
        ).prefetch_related("sections").order_by("order", "pk")
    )
    if not breaks:
        return breaks, [], {}
    if not slots:
        blockers.append({
            "code": "slots_missing",
            "message": "لا يمكن توزيع الاستراحات قبل تعريف أوقات الحصص.",
            "target": "timetable:slot_list",
        })
        return breaks, [], {}

    first_start = _minutes(slots[0].start_time)
    last_end = max(_minutes(slot.end_time) for slot in slots)
    earliest = first_start + BREAK_MARGIN_MINUTES
    latest_end = last_end - BREAK_MARGIN_MINUTES
    boundaries = [(_minutes(slot.end_time), index) for index, slot in enumerate(slots[:-1])]
    section_ids = {section.pk for section in sections}
    seen = defaultdict(list)
    specs = []

    for event in breaks:
        all_selected = list(event.sections.all())
        if not all_selected:
            blockers.append({
                "code": "break_sections_missing",
                "message": f"الاستراحة «{event.name}» لا تحتوي مجموعة شعب.",
                "target": "timetable:schedule_settings",
            })
        selected = [section.pk for section in all_selected if section.pk in section_ids]
        # The existing event model is school-wide, so an event may also contain
        # sections from another open academic year.  Such an event is simply
        # irrelevant to the selected year and must not block its timetable.
        if all_selected and not selected:
            continue
        duration = event.effective_duration_minutes
        if not duration:
            blockers.append({
                "code": "break_duration_missing",
                "message": f"حدد مدة الاستراحة «{event.name}» بالدقائق.",
                "target": "timetable:schedule_settings",
            })
        for day in event.day_codes:
            for section_id in selected:
                seen[(section_id, day)].append(event.name)
        candidates = []
        if duration:
            if event.placement_mode == "fixed":
                if event.start_time and event.end_time:
                    start = _minutes(event.start_time)
                    end = _minutes(event.end_time)
                    matching = [index for boundary, index in boundaries if boundary == start]
                    if not matching:
                        blockers.append({
                            "code": "break_boundary",
                            "message": f"الاستراحة الثابتة «{event.name}» يجب أن تبدأ مباشرة بعد نهاية إحدى الحصص.",
                            "target": "timetable:schedule_settings",
                        })
                    elif end - start != duration:
                        blockers.append({
                            "code": "break_duration_mismatch",
                            "message": f"مدة الاستراحة «{event.name}» لا تطابق وقت البداية والنهاية.",
                            "target": "timetable:schedule_settings",
                        })
                    elif start < earliest or end > latest_end:
                        blockers.append({
                            "code": "break_middle_window",
                            "message": f"الاستراحة «{event.name}» يجب أن تبدأ بعد ساعتين من بداية اليوم وقبل ساعتين من نهايته.",
                            "target": "timetable:schedule_settings",
                        })
                    else:
                        candidates.append((matching[0], start, end))
            else:
                for boundary, index in boundaries:
                    if boundary >= earliest and boundary + duration <= latest_end:
                        candidates.append((index, boundary, boundary + duration))
                if not candidates:
                    blockers.append({
                        "code": "break_no_middle_slot",
                        "message": f"لا يوجد موضع صالح للاستراحة «{event.name}» داخل المجال الأوسط لليوم.",
                        "target": "timetable:slot_list",
                    })
        specs.append({
            "event": event,
            "section_ids": selected,
            "days": set(event.day_codes) & set(CANONICAL_WORKING_DAYS),
            "duration": duration,
            "candidates": candidates,
        })

    for (section_id, day), names in seen.items():
        if len(names) > 1:
            section = next((item for item in sections if item.pk == section_id), None)
            blockers.append({
                "code": "section_multiple_breaks",
                "message": f"الشعبة {section or section_id} موجودة في أكثر من استراحة يوم {DAY_LABELS.get(day, day)}: {', '.join(names)}.",
                "target": "timetable:schedule_settings",
            })

    occupied = defaultdict(list)
    placed = {}
    ordered = sorted(specs, key=lambda item: (len(item["candidates"]) or 9999, item["event"].order, item["event"].pk))

    def place(index):
        if index >= len(ordered):
            return True
        spec = ordered[index]
        candidates = sorted(
            spec["candidates"],
            key=lambda value: (abs(((value[1] + value[2]) // 2) - ((earliest + latest_end) // 2)), value[0]),
        )
        for after_index, start, end in candidates:
            conflict = False
            for day in spec["days"]:
                if any(_overlap(start, end, old_start, old_end) for old_start, old_end in occupied[day]):
                    conflict = True
                    break
            if conflict:
                continue
            for day in spec["days"]:
                occupied[day].append((start, end))
            next_slot_start = _minutes(slots[after_index + 1].start_time)
            placed[spec["event"].pk] = {
                "event": spec["event"],
                "section_ids": spec["section_ids"],
                "days": spec["days"],
                "after_index": after_index,
                "start_minutes": start,
                "end_minutes": end,
                "start_time": _clock(start),
                "end_time": _clock(end),
                "duration": spec["duration"],
                "shift_minutes": max(end - next_slot_start, 0),
            }
            if place(index + 1):
                return True
            placed.pop(spec["event"].pk, None)
            for day in spec["days"]:
                occupied[day].remove((start, end))
        return False

    if specs and all(spec["candidates"] for spec in specs) and not place(0):
        blockers.append({
            "code": "break_courtyard_overlap",
            "message": "تعذر توزيع الاستراحات دون تداخل في الساحة الواحدة داخل المجال الأوسط.",
            "target": "timetable:schedule_settings",
        })

    section_breaks = {}
    for placement in placed.values():
        for section_id in placement["section_ids"]:
            for day in placement["days"]:
                section_breaks[(section_id, day)] = placement
    return breaks, list(placed.values()), section_breaks


def _actual_slot(slot, slot_index, placement):
    shift = placement["shift_minutes"] if placement and slot_index > placement["after_index"] else 0
    return _minutes(slot.start_time) + shift, _minutes(slot.end_time) + shift


def _has_overlap(rows, start, end):
    return any(_overlap(start, end, old_start, old_end) for old_start, old_end in rows)


def _materialize_time_slot(row):
    base = row["base_slot"]
    if row["start_time"] == base.start_time and row["end_time"] == base.end_time:
        return base
    existing = TimeSlot.objects.filter(
        start_time=row["start_time"],
        end_time=row["end_time"],
        order=base.order,
        is_active=True,
    ).first()
    if existing:
        return existing
    return TimeSlot.objects.create(
        name=f"{base.name} — توقيت ذكي",
        start_time=row["start_time"],
        end_time=row["end_time"],
        order=base.order,
        is_active=True,
        generated_for_smart_schedule=True,
    )


def _apply_overrides(*, plan, overrides, existing, days, slots, section_breaks, teacher_day_caps, blockers):
    if not overrides:
        return plan
    slot_by_id = {str(slot.pk): (index, slot) for index, slot in enumerate(slots)}
    section_busy = defaultdict(list)
    teacher_busy = defaultdict(list)
    teacher_daily_count = Counter()
    for row in existing:
        interval = (_minutes(row.time_slot.start_time), _minutes(row.time_slot.end_time))
        section_busy[(row.section_id, row.day)].append(interval)
        if row.teacher_id:
            teacher_busy[(row.teacher_id, row.day)].append(interval)
            teacher_daily_count[(row.teacher_id, row.day)] += 1

    revised = []
    for row in plan:
        assignment = row["assignment"]
        requested = overrides.get(row["row_key"], {})
        day = requested.get("day") or row["day"]
        slot_value = requested.get("slot") or str(row["base_slot"].pk)
        slot_data = slot_by_id.get(str(slot_value))
        error = ""
        if day not in days:
            error = "اليوم المختار ليس ضمن أيام الدوام من الأحد إلى الخميس."
        elif not slot_data:
            error = "وقت الحصة المختار غير متاح."
        else:
            slot_index, slot = slot_data
            placement = section_breaks.get((assignment.section_id, day))
            start, end = _actual_slot(slot, slot_index, placement)
            if _has_overlap(section_busy[(assignment.section_id, day)], start, end):
                error = "الشعبة مرتبطة بحصة أخرى تتداخل مع هذا الوقت."
            elif _has_overlap(teacher_busy[(assignment.teacher_id, day)], start, end):
                error = "المعلم مرتبط بحصة أخرى تتداخل مع هذا الوقت."
            elif teacher_daily_count[(assignment.teacher_id, day)] >= teacher_day_caps[(assignment.teacher_id, day)]:
                error = "هذا النقل يتجاوز الحد اليومي الناتج عن سياسة فراغ المعلم."
        if error:
            blockers.append({
                "code": "manual_override_conflict",
                "message": f"تعذر تعديل {assignment}: {error}",
                "target": "timetable:dashboard",
            })
            row = {**row, "override_error": error}
            # Keep the original proposal visible, but it remains unapprovable.
            day = row["day"]
            slot_index = row["slot_index"]
            slot = row["base_slot"]
            start = row["start_minutes"]
            end = row["end_minutes"]
        else:
            row = {
                **row,
                "day": day,
                "day_label": DAY_LABELS[day],
                "base_slot": slot,
                "slot_index": slot_index,
                "time_slot": slot,
                "period_name": slot.name,
                "start_minutes": start,
                "end_minutes": end,
                "start_time": _clock(start),
                "end_time": _clock(end),
                "overridden": day != row["day"] or slot.pk != row["base_slot"].pk,
            }
        revised.append(row)
        section_busy[(assignment.section_id, day)].append((start, end))
        teacher_busy[(assignment.teacher_id, day)].append((start, end))
        teacher_daily_count[(assignment.teacher_id, day)] += 1
    return revised


def build_smart_timetable(
    *,
    academic_year,
    apply=False,
    replace_generated=False,
    variant="balanced",
    expected_fingerprint="",
    overrides=None,
    enforce_daily_teaching_target=False,
):
    """Build or atomically apply a timetable proposal without a parallel model."""
    overrides = overrides or {}
    settings, _ = SchoolScheduleSettings.objects.get_or_create(school=academic_year.school)
    blockers = []
    warnings = []
    days = [day for day in CANONICAL_WORKING_DAYS if day not in settings.weekend_day_codes]
    if days != CANONICAL_WORKING_DAYS:
        blockers.append({
            "code": "working_days",
            "message": "اضبط أيام الدوام على الأحد إلى الخميس، وأيام العطلة على الجمعة والسبت.",
            "target": "timetable:schedule_settings",
        })

    slots = list(
        TimeSlot.objects.filter(is_active=True, generated_for_smart_schedule=False)
        .order_by("order", "start_time", "pk")
    )
    if not slots:
        blockers.append({
            "code": "slots_missing",
            "message": "أضف أوقات الحصص الأساسية قبل بناء الجدول.",
            "target": "timetable:slot_list",
        })

    assignments = list(
        TeacherAssignment.objects.filter(academic_year=academic_year, is_active=True)
        .select_related("teacher", "section__grade", "subject")
        .order_by("section__grade__order", "section__name", "subject__name", "teacher__full_name")
    )
    plan_subjects = list(
        Subject.objects.filter(academic_year=academic_year, is_active=True)
        .select_related("grade")
        .order_by("grade__order", "name")
    )
    sections = list(
        Section.objects.filter(academic_year=academic_year, is_active=True)
        .select_related("grade")
        .order_by("grade__order", "name")
    )
    plan_map = {(item.grade_id, item.pk): item.weekly_periods for item in plan_subjects}

    by_section_subject = defaultdict(list)
    for assignment in assignments:
        key = (assignment.section_id, assignment.subject_id)
        by_section_subject[key].append(assignment)
        if (assignment.section.grade_id, assignment.subject_id) not in plan_map:
            blockers.append({
                "code": "assignment_without_plan",
                "message": f"التكليف {assignment} لا يملك بندًا فعالًا في الخطة الدراسية.",
                "target": "academics:subject_list",
            })
    for key, rows in by_section_subject.items():
        if len(rows) > 1:
            blockers.append({
                "code": "duplicate_assignment",
                "message": f"يوجد أكثر من معلم مكلف للمادة نفسها في الشعبة: {rows[0].section} — {rows[0].subject}.",
                "target": "teachers:teacher_list",
            })

    for section in sections:
        for subject in plan_subjects:
            if subject.grade_id != section.grade_id:
                continue
            if (section.pk, subject.pk) not in by_section_subject:
                blockers.append({
                    "code": "plan_without_assignment",
                    "message": f"الخطة تتطلب {subject} للشعبة {section} ولا يوجد تكليف فعال.",
                    "target": "teachers:teacher_list",
                })

    breaks, break_placements, section_breaks = _break_specs(
        school=academic_year.school,
        sections=sections,
        slots=slots,
        blockers=blockers,
    )

    base_qs = TimetableEntry.objects.filter(academic_year=academic_year, is_active=True)
    if replace_generated:
        base_qs = base_qs.filter(generated_automatically=False)
    existing = list(
        base_qs.select_related("section", "teacher", "time_slot", "subject")
        .order_by("pk")
    )

    fingerprint = _source_fingerprint(
        academic_year=academic_year,
        assignments=assignments,
        plan_subjects=plan_subjects,
        slots=slots,
        breaks=breaks,
        settings=settings,
        existing=existing,
    )
    if expected_fingerprint and expected_fingerprint != fingerprint:
        raise ValidationError(
            "تغيرت الخطة أو التكليفات أو النصاب أو أوقات الحصص بعد المعاينة. أنشئ اقتراحًا جديدًا قبل الاعتماد."
        )

    assigned_totals, missing_plan_by_teacher = workload_by_teacher(assignments, plan_map)
    capacity = len(days) * len(slots)
    teacher_rows = []
    teachers = {}
    for assignment in assignments:
        teachers[assignment.teacher_id] = assignment.teacher
    teacher_day_caps = {}
    target_daily = {}
    for teacher_id, teacher in sorted(teachers.items(), key=lambda item: item[1].full_name):
        assigned = assigned_totals.get(teacher_id, 0)
        load = teacher.weekly_teaching_load
        if load is None:
            blockers.append({
                "code": "teacher_load_missing",
                "message": f"لم يضبط النصاب الأسبوعي للمعلم {teacher.full_name}.",
                "target": f"teachers:teacher_detail:{teacher.pk}",
            })
        elif assigned > load:
            blockers.append({
                "code": "teacher_load_exceeded",
                "message": f"المعلم {teacher.full_name}: الحصص المسندة {assigned} تتجاوز النصاب {load}.",
                "target": f"teachers:teacher_detail:{teacher.pk}",
            })

        if teacher.free_period_policy == "daily":
            required_free = teacher.daily_free_periods * len(days)
            day_free_targets = {day: teacher.daily_free_periods for day in days}
            if assigned > sum(max(len(slots) - day_free_targets[day], 0) for day in days):
                blockers.append({
                    "code": "daily_free_impossible",
                    "message": f"فراغ {teacher.full_name} اليومي غير قابل للتطبيق مع {assigned} حصة مسندة.",
                    "target": f"teachers:teacher_detail:{teacher.pk}",
                })
        elif teacher.free_period_policy == "weekly":
            required_free = teacher.weekly_free_periods
            base_free, extra_free = divmod(required_free, len(days) or 1)
            # Rotate the days receiving an extra free period so all teachers are not
            # forced into the same light day.  The manager still controls only the
            # weekly number; the engine distributes it.
            offset = teacher_id % len(days) if days else 0
            rotated_days = days[offset:] + days[:offset]
            day_free_targets = {day: base_free for day in days}
            for day in rotated_days[:extra_free]:
                day_free_targets[day] += 1
            if any(value > len(slots) for value in day_free_targets.values()) or assigned > sum(
                max(len(slots) - day_free_targets[day], 0) for day in days
            ):
                blockers.append({
                    "code": "weekly_free_impossible",
                    "message": f"المعلم {teacher.full_name}: {assigned} حصة + {required_free} فراغ لا يمكن توزيعها على أيام الدوام.",
                    "target": f"teachers:teacher_detail:{teacher.pk}",
                })
        else:
            required_free = max(capacity - assigned, 0)
            day_free_targets = {day: 0 for day in days}
        target = math.ceil(assigned / len(days)) if days else assigned
        if enforce_daily_teaching_target and days:
            if assigned % len(days):
                blockers.append({
                    "code": "exact_daily_target_impossible",
                    "message": f"المعلم {teacher.full_name}: لا يمكن توزيع {assigned} حصة بالتساوي على أيام الدوام.",
                    "target": f"teachers:teacher_detail:{teacher.pk}",
                })
            else:
                target = assigned // len(days)
        for day in days:
            cap = max(len(slots) - day_free_targets.get(day, 0), 0)
            if enforce_daily_teaching_target:
                cap = min(cap, target)
            teacher_day_caps[(teacher_id, day)] = cap
        target_daily[teacher_id] = target
        teacher_rows.append({
            "teacher": teacher,
            "load": load,
            "assigned": assigned,
            "remaining": None if load is None else load - assigned,
            "free_required": required_free,
            "daily_cap": min((teacher_day_caps[(teacher_id, day)] for day in days), default=0),
            "daily_cap_max": max((teacher_day_caps[(teacher_id, day)] for day in days), default=0),
            "day_capacity_label": "، ".join(
                f"{DAY_LABELS[day]} {teacher_day_caps[(teacher_id, day)]}" for day in days
            ),
            "missing_plan": missing_plan_by_teacher.get(teacher_id, 0),
            "status": "متجاوز" if load is not None and assigned > load else "غير مضبوط" if load is None else "سليم",
        })

    for row in existing:
        placement = section_breaks.get((row.section_id, row.day))
        if placement and _overlap(
            _minutes(row.time_slot.start_time),
            _minutes(row.time_slot.end_time),
            placement["start_minutes"],
            placement["end_minutes"],
        ):
            blockers.append({
                "code": "existing_entry_break_overlap",
                "message": f"الحصة الحالية {row} تتداخل مع الاستراحة المقترحة «{placement['event'].name}». عدل الحصة أو الاستراحة أولًا.",
                "target": "timetable:dashboard",
            })
    section_busy = defaultdict(list)
    teacher_busy = defaultdict(list)
    same_count = Counter()
    daily_subject_count = Counter()
    teacher_daily_count = Counter()
    for row in existing:
        interval = (_minutes(row.time_slot.start_time), _minutes(row.time_slot.end_time))
        section_busy[(row.section_id, row.day)].append(interval)
        if row.teacher_id:
            teacher_busy[(row.teacher_id, row.day)].append(interval)
            teacher_daily_count[(row.teacher_id, row.day)] += 1
        same_count[(row.section_id, row.subject_id, row.teacher_id)] += 1
        daily_subject_count[(row.section_id, row.subject_id, row.day)] += 1

    plan = []
    unresolved = []
    if not blockers and days and slots:
        for assignment in assignments:
            required = plan_map[(assignment.section.grade_id, assignment.subject_id)]
            key = (assignment.section_id, assignment.subject_id, assignment.teacher_id)
            needed = max(required - same_count[key], 0)
            for occurrence in range(needed):
                candidates = []
                for day_index, day in enumerate(days):
                    if teacher_daily_count[(assignment.teacher_id, day)] >= teacher_day_caps[(assignment.teacher_id, day)]:
                        continue
                    placement = section_breaks.get((assignment.section_id, day))
                    for slot_index, slot in enumerate(slots):
                        start, end = _actual_slot(slot, slot_index, placement)
                        if _has_overlap(section_busy[(assignment.section_id, day)], start, end):
                            continue
                        if _has_overlap(teacher_busy[(assignment.teacher_id, day)], start, end):
                            continue
                        adjacent = sum(
                            1 for old_start, old_end in teacher_busy[(assignment.teacher_id, day)]
                            if old_end == start or old_start == end
                        )
                        daily_teacher = teacher_daily_count[(assignment.teacher_id, day)]
                        daily_subject = daily_subject_count[(assignment.section_id, assignment.subject_id, day)]
                        balance_gap = abs((daily_teacher + 1) - target_daily[assignment.teacher_id])
                        if variant == "compact":
                            score = (-adjacent, daily_subject * 20, daily_teacher, day_index, slot.order, start)
                        elif variant == "spread":
                            score = (daily_teacher * 20, daily_subject * 30, adjacent * 4, day_index, slot.order, start)
                        else:
                            score = (daily_subject * 40, daily_teacher * 8, adjacent * 5, balance_gap, day_index, slot.order, start)
                        candidates.append((score, day, slot_index, slot, start, end))
                if not candidates:
                    unresolved.append({
                        "assignment": assignment,
                        "missing": required - same_count[key],
                        "reason": "لا يوجد وقت خالٍ يحقق النصاب والفراغ والاستراحات دون تعارض.",
                    })
                    break
                _, day, slot_index, slot, start, end = min(candidates, key=lambda item: item[0])
                row = {
                    "row_key": f"{assignment.pk}-{occurrence}",
                    "assignment": assignment,
                    "day": day,
                    "day_label": DAY_LABELS[day],
                    "base_slot": slot,
                    "slot_index": slot_index,
                    "time_slot": slot,
                    "period_name": slot.name,
                    "start_minutes": start,
                    "end_minutes": end,
                    "start_time": _clock(start),
                    "end_time": _clock(end),
                }
                plan.append(row)
                section_busy[(assignment.section_id, day)].append((start, end))
                teacher_busy[(assignment.teacher_id, day)].append((start, end))
                teacher_daily_count[(assignment.teacher_id, day)] += 1
                daily_subject_count[(assignment.section_id, assignment.subject_id, day)] += 1
                same_count[key] += 1

    plan = _apply_overrides(
        plan=plan,
        overrides=overrides,
        existing=existing,
        days=days,
        slots=slots,
        section_breaks=section_breaks,
        teacher_day_caps=teacher_day_caps,
        blockers=blockers,
    )

    if apply and (blockers or unresolved):
        first = blockers[0]["message"] if blockers else unresolved[0]["reason"]
        raise ValidationError(f"تعذر اعتماد الجدول كاملًا: {first} بقي الجدول السابق كما هو.")

    created = []
    if apply:
        with transaction.atomic():
            if replace_generated:
                TimetableEntry.objects.filter(
                    academic_year=academic_year,
                    generated_automatically=True,
                ).delete()
            for placement in break_placements:
                event = placement["event"]
                if event.placement_mode == "smart":
                    event.start_time = placement["start_time"]
                    event.end_time = placement["end_time"]
                    event.save(update_fields=["start_time", "end_time"])
            for row in plan:
                assignment = row["assignment"]
                slot = _materialize_time_slot(row)
                created.append(TimetableEntry.objects.create(
                    academic_year=academic_year,
                    section=assignment.section,
                    subject=assignment.subject,
                    teacher=assignment.teacher,
                    day=row["day"],
                    time_slot=slot,
                    generated_automatically=True,
                ))
            TimeSlot.objects.filter(
                generated_for_smart_schedule=True,
                entries__isnull=True,
            ).delete()

    total_required = sum(plan_map.get((item.section.grade_id, item.subject_id), 0) for item in assignments)
    completed = total_required - sum(item["missing"] for item in unresolved)
    quality = {
        "completion": 100 if not total_required else round(completed * 100 / total_required),
        "conflicts": 0,
        "unresolved": len(unresolved),
        "balanced_teachers": sum(
            1 for row in teacher_rows if row["status"] == "سليم"
        ),
    }
    readiness = {
        "plan": "ok" if plan_subjects and not any(item["code"] in {"assignment_without_plan", "plan_without_assignment"} for item in blockers) else "issue",
        "assignments": "ok" if assignments and not any(item["code"] == "duplicate_assignment" for item in blockers) else "issue",
        "workload": "ok" if teacher_rows and not any("load" in item["code"] or "free" in item["code"] for item in blockers) else "issue",
        "breaks": "ok" if not any(item["code"].startswith("break") or item["code"].startswith("section_multiple") for item in blockers) else "issue",
        "slots": "ok" if slots else "issue",
    }
    return {
        "plan": plan,
        "created": created,
        "unresolved": unresolved,
        "blockers": blockers,
        "warnings": warnings,
        "assignment_count": len(assignments),
        "slot_count": len(slots),
        "working_days": days,
        "working_day_options": [(day, DAY_LABELS[day]) for day in days],
        "base_slots": slots,
        "teacher_rows": teacher_rows,
        "break_placements": break_placements,
        "fingerprint": fingerprint,
        "can_apply": not blockers and not unresolved,
        "readiness": readiness,
        "quality": quality,
        "variant": variant,
        "replace_generated": replace_generated,
        "variant_label": {
            "balanced": "متوازن",
            "compact": "تقليل فراغات المعلمين",
            "spread": "توزيع أوسع على الأيام",
        }.get(variant, "متوازن"),
    }
