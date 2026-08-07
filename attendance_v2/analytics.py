"""Canonical analytics for OPAL's exception-only student attendance.

``Attendance`` stores exceptions only (``absent`` and ``departed``). A valid
``AttendanceRegister`` supplies the daily class roster from which implicit
presence is derived. All dashboards, 360 profiles and exports must use this
module; they must never count removed ``present`` or ``late`` student statuses.
"""

from bisect import bisect_left, bisect_right
from datetime import timedelta

from django.db.models import Q

from academics.models import Enrollment

from .models import Attendance, AttendanceRegister


VALID_REGISTER_Q = (
    Q(submitted_at__isnull=False)
    | Q(is_teacher_locked=True)
    | Q(is_admin_closed=True)
)


def _percentage(value, total):
    if not total:
        return 0
    return round((value / total) * 100, 1)


def _inside_enrollment(row, target_date):
    lower = row["joined_at"] or row["academic_year__start_date"]
    upper = row["ended_at"] or row["academic_year__end_date"]
    return lower <= target_date <= upper


def _empty_day(day):
    return {
        "date": day,
        "roster_total": 0,
        "present": 0,
        "absent": 0,
        "departed": 0,
        "exceptions": 0,
        "percent": 0,
        "submitted_sections": 0,
        "closed_sections": 0,
        "pending_sections": 0,
        "has_data": False,
        # Old/inconsistent exception rows remain measurable for integrity
        # follow-up, but never reduce a roster to which they cannot be tied.
        "unregistered_absent": 0,
        "unregistered_departed": 0,
        "unregistered_exceptions": 0,
        "absent_student_ids": [],
        "departed_student_ids": [],
    }


def build_school_attendance_period_snapshot(start_date, end_date, *, school=None, academic_year=None):
    """Return authoritative daily metrics for an inclusive date range.

    A register is authoritative after submission, teacher lock or administrative
    closure. Its roster is reconstructed from the enrollment interval on that
    exact date, so withdrawn/completed pupils remain correctly represented in
    historical reports. Exceptions are subtracted only when their student,
    section, academic year and date match that authoritative roster.
    """
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")

    daily = {}
    cursor = start_date
    while cursor <= end_date:
        daily[cursor] = _empty_day(cursor)
        cursor += timedelta(days=1)

    register_qs = AttendanceRegister.objects.filter(
        date__gte=start_date,
        date__lte=end_date,
    ).filter(VALID_REGISTER_Q)
    if academic_year is not None:
        register_qs = register_qs.filter(academic_year=academic_year)
    elif school is not None:
        register_qs = register_qs.filter(academic_year__school=school)

    registers = list(
        register_qs.values(
            "date",
            "section_id",
            "academic_year_id",
            "is_admin_closed",
        )
    )
    register_keys = {
        (row["date"], row["section_id"], row["academic_year_id"])
        for row in registers
    }
    section_ids = {row["section_id"] for row in registers}
    year_ids = {row["academic_year_id"] for row in registers}

    enrollment_rows = []
    if section_ids and year_ids:
        enrollment_rows = list(
            Enrollment.objects.filter(
                section_id__in=section_ids,
                academic_year_id__in=year_ids,
            ).values(
                "student_id",
                "section_id",
                "academic_year_id",
                "academic_year__start_date",
                "academic_year__end_date",
                "joined_at",
                "ended_at",
            )
        )

    enrollments_by_section_year = {}
    for row in enrollment_rows:
        enrollments_by_section_year.setdefault(
            (row["section_id"], row["academic_year_id"]),
            [],
        ).append(row)

    roster_by_register = {}
    for row in registers:
        key = (row["date"], row["section_id"], row["academic_year_id"])
        roster = {
            enrollment["student_id"]
            for enrollment in enrollments_by_section_year.get(
                (row["section_id"], row["academic_year_id"]),
                [],
            )
            if _inside_enrollment(enrollment, row["date"])
        }
        roster_by_register[key] = roster

        day = daily[row["date"]]
        day["roster_total"] += len(roster)
        day["submitted_sections"] += 1
        if row["is_admin_closed"]:
            day["closed_sections"] += 1
        else:
            day["pending_sections"] += 1
        day["has_data"] = True

    exception_qs = Attendance.objects.filter(
        date__gte=start_date,
        date__lte=end_date,
        status__in=["absent", "departed"],
    )
    if academic_year is not None:
        exception_qs = exception_qs.filter(academic_year=academic_year)
    elif school is not None:
        exception_qs = exception_qs.filter(academic_year__school=school)

    for row in exception_qs.values(
        "student_id",
        "date",
        "status",
        "section_id",
        "academic_year_id",
    ):
        key = (row["date"], row["section_id"], row["academic_year_id"])
        if key in register_keys and row["student_id"] in roster_by_register.get(key, set()):
            daily[row["date"]][row["status"]] += 1
            daily[row["date"]][f'{row["status"]}_student_ids'].append(row["student_id"])
        else:
            daily[row["date"]][f'unregistered_{row["status"]}'] += 1

    totals = {
        "roster_total": 0,
        "present": 0,
        "absent": 0,
        "departed": 0,
        "exceptions": 0,
        "percent": 0,
        "submitted_sections": 0,
        "closed_sections": 0,
        "pending_sections": 0,
        "has_data": False,
        "unregistered_absent": 0,
        "unregistered_departed": 0,
        "unregistered_exceptions": 0,
    }
    additive_keys = (
        "roster_total",
        "present",
        "absent",
        "departed",
        "exceptions",
        "submitted_sections",
        "closed_sections",
        "pending_sections",
        "unregistered_absent",
        "unregistered_departed",
        "unregistered_exceptions",
    )
    for day in daily.values():
        day["exceptions"] = day["absent"] + day["departed"]
        day["unregistered_exceptions"] = (
            day["unregistered_absent"] + day["unregistered_departed"]
        )
        day["present"] = max(day["roster_total"] - day["exceptions"], 0)
        day["percent"] = _percentage(day["present"], day["roster_total"])
        for key in additive_keys:
            totals[key] += day[key]
        totals["has_data"] = totals["has_data"] or day["has_data"]
    totals["percent"] = _percentage(totals["present"], totals["roster_total"])

    return {
        "start_date": start_date,
        "end_date": end_date,
        "days": daily,
        "totals": totals,
    }


def build_student_attendance_summaries(students, *, start_date=None, end_date=None):
    """Build attendance summaries for many students without N+1 queries.

    The rate denominator is the union of authoritative register dates and any
    legacy exception dates. This keeps old genuine absences visible without
    inventing present days for periods that have no submitted register.
    """
    students = list(students)
    if not students:
        return {}

    student_ids = [student.pk for student in students]
    enrollment_rows = list(
        Enrollment.objects.filter(
            student_id__in=student_ids,
            section__isnull=False,
        ).values(
            "student_id",
            "academic_year_id",
            "academic_year__start_date",
            "academic_year__end_date",
            "section_id",
            "joined_at",
            "ended_at",
        )
    )

    section_ids = {row["section_id"] for row in enrollment_rows}
    year_ids = {row["academic_year_id"] for row in enrollment_rows}
    register_dates_by_key = {}
    if section_ids and year_ids:
        register_qs = AttendanceRegister.objects.filter(
            section_id__in=section_ids,
            academic_year_id__in=year_ids,
        ).filter(VALID_REGISTER_Q)
        if start_date is not None:
            register_qs = register_qs.filter(date__gte=start_date)
        if end_date is not None:
            register_qs = register_qs.filter(date__lte=end_date)
        for row in register_qs.values("academic_year_id", "section_id", "date"):
            register_dates_by_key.setdefault(
                (row["academic_year_id"], row["section_id"]),
                set(),
            ).add(row["date"])
        register_dates_by_key = {
            key: sorted(values)
            for key, values in register_dates_by_key.items()
        }

    registered_dates = {student_id: set() for student_id in student_ids}
    for row in enrollment_rows:
        lower = row["joined_at"] or row["academic_year__start_date"]
        upper = row["ended_at"] or row["academic_year__end_date"]
        if start_date is not None:
            lower = max(lower, start_date)
        if end_date is not None:
            upper = min(upper, end_date)
        if upper < lower:
            continue
        dates = register_dates_by_key.get(
            (row["academic_year_id"], row["section_id"]),
            [],
        )
        left = bisect_left(dates, lower)
        right = bisect_right(dates, upper)
        registered_dates[row["student_id"]].update(dates[left:right])

    exception_qs = Attendance.objects.filter(
        student_id__in=student_ids,
        status__in=["absent", "departed"],
    )
    if start_date is not None:
        exception_qs = exception_qs.filter(date__gte=start_date)
    if end_date is not None:
        exception_qs = exception_qs.filter(date__lte=end_date)

    exception_dates = {student_id: set() for student_id in student_ids}
    exception_counts = {
        student_id: {"absent": 0, "departed": 0}
        for student_id in student_ids
    }
    for row in exception_qs.values("student_id", "date", "status"):
        exception_dates[row["student_id"]].add(row["date"])
        exception_counts[row["student_id"]][row["status"]] += 1

    result = {}
    for student_id in student_ids:
        roster_dates = registered_dates[student_id]
        recorded_exception_dates = exception_dates[student_id]
        all_counted_dates = roster_dates | recorded_exception_dates
        absent = exception_counts[student_id]["absent"]
        departed = exception_counts[student_id]["departed"]
        exceptions = absent + departed
        present = len(roster_dates - recorded_exception_dates)
        total = len(all_counted_dates)
        result[student_id] = {
            "counts": {
                "present": present,
                "absent": absent,
                "departed": departed,
            },
            "total": total,
            "registered_days": len(roster_dates),
            "legacy_exception_days": len(recorded_exception_dates - roster_dates),
            "present_count": present,
            "absent_count": absent,
            "departed_count": departed,
            "exceptions_count": exceptions,
            "rate": _percentage(present, total),
        }
    return result


def build_student_attendance_snapshot(student, *, start_date=None, end_date=None, recent_limit=60):
    summary = build_student_attendance_summaries(
        [student],
        start_date=start_date,
        end_date=end_date,
    )[student.pk]
    recent_qs = Attendance.objects.filter(
        student=student,
        status__in=["absent", "departed"],
    ).order_by("-date")
    if start_date is not None:
        recent_qs = recent_qs.filter(date__gte=start_date)
    if end_date is not None:
        recent_qs = recent_qs.filter(date__lte=end_date)
    summary["recent"] = list(recent_qs[:recent_limit])
    return summary
