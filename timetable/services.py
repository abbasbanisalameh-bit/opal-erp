from collections import Counter

from django.db import transaction

from teachers.models import TeacherAssignment

from .models import SchoolScheduleSettings, TimeSlot, TimetableEntry


def build_smart_timetable(*, academic_year, apply=False, replace_generated=False):
    """Greedy, deterministic builder that never overwrites a manual entry."""
    settings, _ = SchoolScheduleSettings.objects.get_or_create(school=academic_year.school)
    days = [code for code, _ in TimetableEntry.DAYS if code not in settings.weekend_day_codes]
    slots = list(TimeSlot.objects.filter(is_active=True).order_by("order", "start_time"))
    assignments = list(
        TeacherAssignment.objects.filter(academic_year=academic_year, is_active=True)
        .select_related("teacher", "section", "subject")
        .order_by("section__grade__order", "section__name", "subject__name")
    )
    base_qs = TimetableEntry.objects.filter(academic_year=academic_year, is_active=True)
    if replace_generated:
        base_qs = base_qs.filter(generated_automatically=False)
    existing = list(base_qs.select_related("section", "teacher", "time_slot"))
    section_busy = {(row.section_id, row.day, row.time_slot_id) for row in existing}
    teacher_busy = {(row.teacher_id, row.day, row.time_slot_id) for row in existing if row.teacher_id}
    same_count = Counter((row.section_id, row.subject_id, row.teacher_id) for row in existing)
    daily_count = Counter((row.section_id, row.subject_id, row.teacher_id, row.day) for row in existing)
    slot_load = Counter((row.day, row.time_slot_id) for row in existing)
    plan, unresolved = [], []

    for assignment in assignments:
        key = (assignment.section_id, assignment.subject_id, assignment.teacher_id)
        needed = max(assignment.weekly_periods - same_count[key], 0)
        for _ in range(needed):
            candidates = sorted(
                ((day, slot) for day in days for slot in slots),
                key=lambda value: (daily_count[key + (value[0],)], slot_load[(value[0], value[1].pk)], days.index(value[0]), value[1].order),
            )
            selected = next((value for value in candidates if
                (assignment.section_id, value[0], value[1].pk) not in section_busy and
                (assignment.teacher_id, value[0], value[1].pk) not in teacher_busy
            ), None)
            if not selected:
                unresolved.append({"assignment": assignment, "missing": assignment.weekly_periods - same_count[key]})
                break
            day, slot = selected
            plan.append({"assignment": assignment, "day": day, "time_slot": slot})
            section_busy.add((assignment.section_id, day, slot.pk))
            teacher_busy.add((assignment.teacher_id, day, slot.pk))
            daily_count[key + (day,)] += 1
            slot_load[(day, slot.pk)] += 1
            same_count[key] += 1

    if apply:
        with transaction.atomic():
            if replace_generated:
                TimetableEntry.objects.filter(academic_year=academic_year, generated_automatically=True).delete()
            created = []
            for row in plan:
                assignment = row["assignment"]
                created.append(TimetableEntry.objects.create(
                    academic_year=academic_year, section=assignment.section, subject=assignment.subject,
                    teacher=assignment.teacher, day=row["day"], time_slot=row["time_slot"],
                    generated_automatically=True,
                ))
    else:
        created = []
    return {
        "plan": plan, "created": created, "unresolved": unresolved,
        "assignment_count": len(assignments), "slot_count": len(slots), "working_days": days,
    }
