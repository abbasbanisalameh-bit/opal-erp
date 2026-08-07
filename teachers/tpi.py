"""The single, evidence-based Teacher Performance Index (TPI) engine.

TPI intentionally reads only official OPAL business records.  It never uses
page visits, clicks, or time spent on a screen.  Open-month values can change
as authorised records are completed; once a monthly snapshot is closed, the
stored score, rank and evidence are never recalculated.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q
from django.utils import timezone

from academics.models import Section
from attendance_v2.models import AttendanceRegister
from core.models import AcademicYear
from exams.models import Exam, StudentMark
from parent_portal.models import TeacherMonthlyEvaluation
from timetable.models import SchoolScheduleSettings, TeacherAbsence

from .models import Homework, Teacher, TeacherAssignment, TeacherPerformanceSnapshot


TPI_VERSION = "TPI-131"
MINIMUM_RANK_EVIDENCE_COVERAGE = Decimal("40.00")

# Fixed, code-owned weights. They deliberately do not live in school settings.
TPI_WEIGHTS = {
    "parent_evaluation": Decimal("18.00"),
    "work_attendance": Decimal("22.00"),
    "student_results": Decimal("15.00"),
    "success_and_improvement": Decimal("15.00"),
    "homework": Decimal("10.00"),
    "marks_timeliness": Decimal("10.00"),
    "student_attendance": Decimal("5.00"),
    "verified_system_activity": Decimal("5.00"),
}

FINAL_EXAM_STATUSES = ("approved", "published", "closed")
APPROVED_NON_PENALTY_WORK_STATUSES = {"approved_excuse", "official_mission"}
WORK_STATUS_SCORES = {
    "present": Decimal("100"),
    "late": Decimal("70"),
    "early_departure": Decimal("70"),
    "absent": Decimal("0"),
}
DAY_CODES = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def month_start(value: date | None = None) -> date:
    value = value or timezone.localdate()
    return value.replace(day=1)


def month_end(period: date) -> date:
    next_month = (period.replace(day=28) + timedelta(days=4)).replace(day=1)
    return next_month - timedelta(days=1)


def _month_window(period: date) -> tuple[date, date, datetime, datetime]:
    start = month_start(period)
    end = month_end(start)
    lower = timezone.make_aware(datetime.combine(start, time.min))
    upper = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min))
    return start, end, lower, upper


def _number(value) -> float:
    if value is None:
        return 0.0
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _percent(value: Decimal | float | int) -> Decimal:
    return max(Decimal("0"), min(Decimal("100"), Decimal(str(value)))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _component(key: str, label: str, score: Decimal | None, summary: str, **details) -> dict:
    weight = TPI_WEIGHTS[key]
    available = score is not None
    normalized = _percent(score) if available else None
    points = ((weight * normalized) / Decimal("100")) if available else Decimal("0")
    return {
        "key": key,
        "label": label,
        "weight": _number(weight),
        "available": available,
        "score": _number(normalized) if normalized is not None else None,
        "points": _number(points),
        "summary": summary,
        "details": details,
    }


def _academic_year_for(teacher: Teacher, period: date) -> AcademicYear | None:
    start, end, _lower, _upper = _month_window(period)
    return (
        AcademicYear.objects.filter(
            school=teacher.school,
            start_date__lte=end,
            end_date__gte=start,
        )
        .order_by("-is_current", "-start_date")
        .first()
    )


def _teacher_scope_for_period(school, period: date):
    end = month_end(period)
    return Teacher.objects.filter(school=school).filter(
        Q(is_active=True) | Q(end_date__isnull=False, end_date__gte=period)
    ).filter(Q(hire_date__isnull=True) | Q(hire_date__lte=end)).order_by("full_name")


def _parent_evaluation_component(teacher: Teacher, period: date) -> dict:
    rows = TeacherMonthlyEvaluation.objects.filter(teacher=teacher, period=period)
    values = list(rows.values_list("teaching_quality_rating", flat=True))
    if not values:
        return _component(
            "parent_evaluation",
            "تقييمات أولياء الأمور",
            None,
            "لا توجد تقييمات أولياء أمور معتمدة لهذا الشهر.",
            responses=0,
        )
    average = sum(Decimal(value) for value in values) / Decimal(len(values))
    return _component(
        "parent_evaluation",
        "تقييمات أولياء الأمور",
        average * Decimal("20"),
        f"متوسط تقييم أولياء الأمور {_number(average)}/5 من {len(values)} تقييمًا.",
        responses=len(values),
        average=_number(average),
    )


def _work_attendance_component(
    teacher: Teacher,
    period: date,
    academic_year: AcademicYear | None,
    today: date,
) -> dict:
    """Apply the official exception policy: no exception means present.

    The component uses elapsed official working days, excludes approved excuse
    and official-mission days from the denominator, and never creates synthetic
    attendance rows merely to feed TPI.
    """
    working_days = set(_school_working_days(teacher, academic_year, period, as_of=today))
    if not working_days:
        return _component(
            "work_attendance", "انتظام الدوام", None,
            "لا توجد أيام دوام رسمية منقضية قابلة للقياس في هذا الشهر.",
            expected_days=0, exception_days=0, excluded_days=0,
        )
    records = list(TeacherAbsence.objects.filter(teacher=teacher, date__in=working_days).order_by("date"))
    records_by_date = {item.date: item for item in records}
    excluded_days = {
        item.date for item in records
        if item.attendance_status in APPROVED_NON_PENALTY_WORK_STATUSES and item.is_approved
    }
    measurable_days = sorted(working_days - excluded_days)
    if not measurable_days:
        return _component(
            "work_attendance", "انتظام الدوام", None,
            "كل أيام الدوام المنقضية مستثناة بعذر أو مهمة رسمية معتمدة.",
            expected_days=len(working_days), exception_days=len(records), excluded_days=len(excluded_days),
        )
    counts = {status: 0 for status, _label in TeacherAbsence.ATTENDANCE_STATUSES}
    values = []
    implicit_present = 0
    for day in measurable_days:
        item = records_by_date.get(day)
        if item is None:
            implicit_present += 1
            values.append(Decimal("100"))
            continue
        counts[item.attendance_status] = counts.get(item.attendance_status, 0) + 1
        values.append(WORK_STATUS_SCORES.get(item.attendance_status, Decimal("0")))
    score = sum(values) / Decimal(len(values))
    return _component(
        "work_attendance",
        "انتظام الدوام",
        score,
        (
            f"حُسب المؤشر وفق استثناءات الدوام المعتمدة إداريًا خلال {len(measurable_days)} يومًا؛ "
            f"عدم وجود استثناء يعني حاضرًا، ولا تُنشأ سجلات حضور تلقائية."
        ),
        expected_days=len(working_days),
        measurable_days=len(measurable_days),
        exception_days=len(records),
        implicit_present_days=implicit_present,
        excluded_days=len(excluded_days),
        statuses=counts,
        evidence_source="وفق استثناءات الدوام المعتمدة إداريًا",
    )


def _published_marks_for_period(teacher: Teacher, period: date):
    start, end, lower, upper = _month_window(period)
    timing = Q(exam__published_at__gte=lower, exam__published_at__lt=upper) | Q(
        exam__published_at__isnull=True,
        exam__exam_date__range=(start, end),
    )
    return list(
        StudentMark.objects.filter(
            exam__teacher_assignment__teacher=teacher,
            exam__status__in=FINAL_EXAM_STATUSES,
        )
        .filter(timing)
        .select_related("exam", "exam__teacher_assignment")
        .order_by("exam__published_at", "exam__exam_date", "pk")
    )


def _mark_effective_moment(mark: StudentMark) -> datetime:
    published_at = mark.exam.published_at
    if published_at:
        return published_at
    return timezone.make_aware(datetime.combine(mark.exam.exam_date, time.min))


def _previous_percentages_for_marks(current_rows: list[tuple[StudentMark, Decimal]], period: date) -> dict[int, Decimal]:
    """Return the immediate prior result for every current mark in two queries total.

    The old implementation issued one query per student mark, which made the
    teacher and manager TPI pages progressively slower as exam data grew.
    Grouping official marks by student and teaching assignment preserves the
    same comparison rule without N+1 database access.
    """

    if not current_rows:
        return {}
    _start, end, _lower, upper = _month_window(period)
    student_ids = {item.student_id for item, _percentage in current_rows}
    assignment_ids = {
        item.exam.teacher_assignment_id
        for item, _percentage in current_rows
        if item.exam.teacher_assignment_id
    }
    if not student_ids or not assignment_ids:
        return {}

    history_timing = Q(exam__published_at__lt=upper) | Q(
        exam__published_at__isnull=True,
        exam__exam_date__lte=end,
    )
    history = list(
        StudentMark.objects.filter(
            student_id__in=student_ids,
            exam__teacher_assignment_id__in=assignment_ids,
            exam__status__in=FINAL_EXAM_STATUSES,
        )
        .filter(history_timing)
        .select_related("exam", "exam__teacher_assignment")
    )

    grouped: dict[tuple[int, int], list[StudentMark]] = {}
    for item in history:
        assignment_id = item.exam.teacher_assignment_id
        if not assignment_id or not item.exam.max_mark:
            continue
        grouped.setdefault((item.student_id, assignment_id), []).append(item)

    previous_by_mark_id: dict[int, Decimal] = {}
    for rows in grouped.values():
        rows.sort(key=lambda item: (_mark_effective_moment(item), item.pk))
        previous_percentage = None
        for item in rows:
            if previous_percentage is not None:
                previous_by_mark_id[item.pk] = previous_percentage
            previous_percentage = (
                Decimal(item.mark) * Decimal("100") / Decimal(item.exam.max_mark)
            )
    return previous_by_mark_id


def _academic_metrics(teacher: Teacher, period: date) -> dict:
    marks = _published_marks_for_period(teacher, period)
    current_rows = [
        (item, Decimal(item.mark) * Decimal("100") / Decimal(item.exam.max_mark))
        for item in marks
        if item.exam.max_mark
    ]
    if not current_rows:
        return {"available": False, "marks": 0, "average": None, "pass_rate": None, "improvement": None}

    percentages = [percentage for _item, percentage in current_rows]
    average = sum(percentages) / Decimal(len(percentages))
    passed = sum(
        1
        for item, percentage in current_rows
        if percentage >= Decimal(item.exam.pass_percentage)
    )
    pass_rate = Decimal(passed * 100) / Decimal(len(percentages))

    previous_by_mark_id = _previous_percentages_for_marks(current_rows, period)
    deltas = [
        percentage - previous_by_mark_id[item.pk]
        for item, percentage in current_rows
        if item.pk in previous_by_mark_id
    ]
    # Zero change is neutral (50); each percentage-point change moves the
    # improvement signal by five points, capped to a normal 0..100 scale.
    improvement = None
    if deltas:
        improvement = _percent(Decimal("50") + (sum(deltas) / Decimal(len(deltas))) * Decimal("5"))
    return {
        "available": True,
        "marks": len(percentages),
        "average": _percent(average),
        "pass_rate": _percent(pass_rate),
        "improvement": improvement,
        "compared_students": len(deltas),
    }


def _academic_components(teacher: Teacher, period: date) -> tuple[dict, dict]:
    metrics = _academic_metrics(teacher, period)
    if not metrics["available"]:
        unavailable = _component(
            "student_results",
            "متوسط علامات الطلبة",
            None,
            "لا توجد نتائج امتحانية منشورة أو مغلقة لهذا الشهر.",
            marks=0,
        )
        return unavailable, _component(
            "success_and_improvement",
            "النجاح والتحسن",
            None,
            "لا توجد نتائج امتحانية منشورة أو مغلقة لهذا الشهر.",
            marks=0,
        )
    results_component = _component(
        "student_results",
        "متوسط علامات الطلبة",
        metrics["average"],
        f"متوسط نتائج {metrics['marks']} علامة هو {_number(metrics['average'])}%.",
        marks=metrics["marks"],
        average=_number(metrics["average"]),
    )
    improvement = metrics["improvement"]
    success_score = metrics["pass_rate"] if improvement is None else (
        metrics["pass_rate"] * Decimal("0.60") + improvement * Decimal("0.40")
    )
    comparison_note = (
        "لا توجد نتيجة سابقة قابلة للمقارنة؛ احتسبت نسبة النجاح فقط."
        if improvement is None
        else f"شمل التحسن {metrics['compared_students']} مقارنة فردية."
    )
    success_component = _component(
        "success_and_improvement",
        "النجاح والتحسن",
        success_score,
        f"نسبة النجاح {_number(metrics['pass_rate'])}%. {comparison_note}",
        pass_rate=_number(metrics["pass_rate"]),
        improvement_score=_number(improvement) if improvement is not None else None,
        compared_students=metrics["compared_students"],
    )
    return results_component, success_component


def _homework_component(teacher: Teacher, period: date, academic_year: AcademicYear | None) -> tuple[dict, int, bool]:
    _start, _end, lower, upper = _month_window(period)
    assignments = TeacherAssignment.objects.filter(teacher=teacher, is_active=True)
    if academic_year:
        assignments = assignments.filter(academic_year=academic_year)
    assignment_ids = list(assignments.values_list("pk", flat=True))
    if not assignment_ids:
        return _component("homework", "إدخال الواجبات", None, "لا توجد تكليفات تدريسية فعالة في هذا الشهر.", assignments=0), 0, False
    covered_ids = set(
        Homework.objects.filter(
            assignment_id__in=assignment_ids,
            created_at__gte=lower,
            created_at__lt=upper,
            is_active=True,
        ).values_list("assignment_id", flat=True)
    )
    score = Decimal(len(covered_ids) * 100) / Decimal(len(assignment_ids))
    return _component(
        "homework",
        "إدخال الواجبات",
        score,
        f"تم إدخال واجب فعلي في {len(covered_ids)} من {len(assignment_ids)} تكليفات نشطة.",
        assignments=len(assignment_ids),
        covered_assignments=len(covered_ids),
    ), len(covered_ids), True


def _marks_timeliness_component(teacher: Teacher, period: date, today: date) -> tuple[dict, int, bool]:
    start, end, _lower, _upper = _month_window(period)
    as_of = min(today, end)
    exams = list(
        Exam.objects.filter(
            teacher_assignment__teacher=teacher,
            marks_due_date__range=(start, as_of),
            is_active=True,
        ).select_related("teacher_assignment")
    )
    if not exams:
        return _component(
            "marks_timeliness",
            "إدخال العلامات ضمن المواعيد",
            None,
            "لا توجد مواعيد إدخال علامات مستحقة لهذا الشهر.",
            due_exams=0,
        ), 0, False
    timely = sum(
        1
        for exam in exams
        if exam.submitted_at and timezone.localtime(exam.submitted_at).date() <= exam.marks_due_date
    )
    score = Decimal(timely * 100) / Decimal(len(exams))
    return _component(
        "marks_timeliness",
        "إدخال العلامات ضمن المواعيد",
        score,
        f"أُرسلت {timely} من {len(exams)} امتحانات قبل أو في موعد إدخال العلامات المعتمد.",
        due_exams=len(exams),
        timely_exams=timely,
    ), timely, True


def _school_working_days(
    teacher: Teacher,
    academic_year: AcademicYear | None,
    period: date,
    *,
    as_of: date | None = None,
) -> list[date]:
    start, end, _lower, _upper = _month_window(period)
    if academic_year:
        start = max(start, academic_year.start_date)
        end = min(end, academic_year.end_date)
    if as_of is not None:
        end = min(end, as_of)
    if end < start:
        return []
    settings = SchoolScheduleSettings.objects.filter(school=teacher.school).first()
    weekends = settings.weekend_day_codes if settings else {"thursday", "friday"}
    dates = []
    current = start
    while current <= end:
        in_midyear_break = bool(
            academic_year
            and academic_year.midyear_break_start
            and academic_year.midyear_break_end
            and academic_year.midyear_break_start <= current <= academic_year.midyear_break_end
        )
        if DAY_CODES[current.weekday()] not in weekends and not in_midyear_break:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def _student_attendance_component(teacher: Teacher, period: date, academic_year: AcademicYear | None, today: date) -> tuple[dict, int, bool]:
    if not teacher.user_id or not academic_year:
        return _component(
            "student_attendance",
            "تسجيل غياب ومغادرة الطلبة",
            None,
            "لا توجد شعبة صفية أو حساب معلم صالح لقياس تسجيل الحضور.",
            expected_registers=0,
        ), 0, False
    sections = Section.objects.filter(
        homeroom_teacher=teacher,
        academic_year=academic_year,
        is_active=True,
    )
    section_ids = list(sections.values_list("pk", flat=True))
    if not section_ids:
        return _component(
            "student_attendance",
            "تسجيل غياب ومغادرة الطلبة",
            None,
            "المعلم ليس مربي شعبة فعالة خلال هذا الشهر.",
            expected_registers=0,
        ), 0, False
    start, end, lower, upper = _month_window(period)
    working_days = set(_school_working_days(teacher, academic_year, period, as_of=today))
    approved_exception_days = set(
        TeacherAbsence.objects.filter(
            teacher=teacher,
            date__range=(start, end),
            attendance_status__in=APPROVED_NON_PENALTY_WORK_STATUSES,
            is_approved=True,
        ).values_list("date", flat=True)
    )
    expected_days = working_days - approved_exception_days
    expected = len(expected_days) * len(section_ids)
    if not expected:
        return _component(
            "student_attendance",
            "تسجيل غياب ومغادرة الطلبة",
            None,
            "لا توجد أيام تدريس مطلوبة بعد استثناء الإجازات والأعذار والمهام المعتمدة.",
            expected_registers=0,
        ), 0, False
    submitted = (
        AttendanceRegister.objects.filter(
            section_id__in=section_ids,
            submitted_by_id=teacher.user_id,
            submitted_at__gte=lower,
            submitted_at__lt=upper,
            date__in=expected_days,
        )
        .values("section_id", "date")
        .distinct()
        .count()
    )
    score = Decimal(min(submitted, expected) * 100) / Decimal(expected)
    return _component(
        "student_attendance",
        "تسجيل غياب ومغادرة الطلبة",
        score,
        f"تم حفظ {submitted} من {expected} سجلات شعبة/يوم مطلوبة، دون احتساب فتح الصفحة كسجل عمل.",
        expected_registers=expected,
        submitted_registers=submitted,
        excluded_teacher_days=len(approved_exception_days),
    ), submitted, True


def _verified_activity_component(
    *, homework_events: int, homework_applicable: bool,
    timely_mark_events: int, marks_applicable: bool,
    attendance_events: int, attendance_applicable: bool,
) -> dict:
    categories = []
    if homework_applicable:
        categories.append(("واجبات", homework_events > 0))
    if marks_applicable:
        categories.append(("علامات", timely_mark_events > 0))
    if attendance_applicable:
        categories.append(("حضور الطلبة", attendance_events > 0))
    if not categories:
        return _component(
            "verified_system_activity",
            "النشاط الحقيقي داخل النظام",
            None,
            "لا توجد عمليات مدرسية مستحقة لقياس النشاط الحقيقي هذا الشهر.",
            categories=[],
        )
    completed = sum(1 for _label, complete in categories if complete)
    score = Decimal(completed * 100) / Decimal(len(categories))
    return _component(
        "verified_system_activity",
        "النشاط الحقيقي داخل النظام",
        score,
        f"استُخدمت {completed} من {len(categories)} فئات عمل مدرسية فعلية؛ لا تدخل النقرات أو مدة فتح الصفحة في الحساب.",
        categories=[{"label": label, "complete": complete} for label, complete in categories],
    )


def build_tpi_evidence(teacher: Teacher, period: date, *, today: date | None = None) -> tuple[dict, list[str], AcademicYear | None]:
    period = month_start(period)
    today = today or timezone.localdate()
    academic_year = _academic_year_for(teacher, period)
    parent = _parent_evaluation_component(teacher, period)
    work = _work_attendance_component(teacher, period, academic_year, today)
    results, success = _academic_components(teacher, period)
    homework, homework_events, homework_applicable = _homework_component(teacher, period, academic_year)
    timeliness, timely_events, marks_applicable = _marks_timeliness_component(teacher, period, today)
    student_attendance, attendance_events, attendance_applicable = _student_attendance_component(teacher, period, academic_year, today)
    activity = _verified_activity_component(
        homework_events=homework_events,
        homework_applicable=homework_applicable,
        timely_mark_events=timely_events,
        marks_applicable=marks_applicable,
        attendance_events=attendance_events,
        attendance_applicable=attendance_applicable,
    )
    components = [parent, work, results, success, homework, timeliness, student_attendance, activity]
    available_weight = sum(
        Decimal(str(component["weight"])) for component in components if component["available"]
    )
    weighted_points = sum(
        Decimal(str(component["points"])) for component in components if component["available"]
    )
    score = (weighted_points * Decimal("100") / available_weight) if available_weight else Decimal("0")
    coverage = available_weight
    improvements = []
    for component in components:
        if not component["available"]:
            improvements.append(f"استكمال بيانات: {component['label']}.")
        elif Decimal(str(component["score"])) < Decimal("80"):
            improvements.append(f"تحسين: {component['label']} ({component['score']}%).")
    payload = {
        "version": TPI_VERSION,
        "score": _number(_percent(score)),
        "evidence_coverage": _number(coverage),
        "components": components,
        "rank_eligible": coverage >= MINIMUM_RANK_EVIDENCE_COVERAGE,
    }
    return payload, improvements[:5], academic_year


def calculate_open_snapshot(teacher: Teacher, period: date, *, today: date | None = None) -> TeacherPerformanceSnapshot:
    period = month_start(period)
    snapshot, _created = TeacherPerformanceSnapshot.objects.get_or_create(
        teacher=teacher,
        period=period,
        defaults={"calculation_version": TPI_VERSION},
    )
    if snapshot.is_closed:
        return snapshot
    evidence, improvements, academic_year = build_tpi_evidence(teacher, period, today=today)
    snapshot.academic_year = academic_year
    snapshot.score = Decimal(str(evidence["score"]))
    snapshot.evidence_coverage = Decimal(str(evidence["evidence_coverage"]))
    snapshot.components = evidence
    snapshot.improvement_actions = improvements
    snapshot.calculation_version = TPI_VERSION
    snapshot.save()
    return snapshot


def _rank_open_snapshots(*, school, period: date) -> list[TeacherPerformanceSnapshot]:
    snapshots = list(
        TeacherPerformanceSnapshot.objects.filter(
            teacher__school=school,
            period=period,
            is_closed=False,
        ).select_related("teacher").order_by("-score", "teacher__full_name", "teacher_id")
    )
    eligible = [
        snapshot for snapshot in snapshots
        if snapshot.evidence_coverage >= MINIMUM_RANK_EVIDENCE_COVERAGE
    ]
    eligible_ids = {snapshot.pk for snapshot in eligible}
    for rank, snapshot in enumerate(eligible, start=1):
        if snapshot.rank != rank:
            snapshot.rank = rank
            snapshot.save(update_fields=["rank", "calculated_at"])
    for snapshot in snapshots:
        if snapshot.pk not in eligible_ids and snapshot.rank is not None:
            snapshot.rank = None
            snapshot.save(update_fields=["rank", "calculated_at"])
    return snapshots


def refresh_school_open_tpi(*, school, period: date | None = None, today: date | None = None) -> list[TeacherPerformanceSnapshot]:
    period = month_start(period)
    today = today or timezone.localdate()
    for teacher in _teacher_scope_for_period(school, period):
        calculate_open_snapshot(teacher, period, today=today)
    return _rank_open_snapshots(school=school, period=period)


def close_tpi_month(
    *,
    school,
    period: date,
    closed_at=None,
    today: date | None = None,
) -> list[TeacherPerformanceSnapshot]:
    """Calculate, rank and freeze one month without mutating source records."""
    period = month_start(period)
    snapshots = refresh_school_open_tpi(
        school=school,
        period=period,
        today=today or timezone.localdate(),
    )
    closed_at = closed_at or timezone.now()
    for snapshot in snapshots:
        if not snapshot.is_closed:
            snapshot.is_closed = True
            snapshot.closed_at = closed_at
            snapshot.save(update_fields=["is_closed", "closed_at", "calculated_at"])
    return snapshots


def close_previous_month_if_needed(*, school, today: date | None = None) -> None:
    """Close the preceding month unless every existing snapshot is closed.

    Checking for the mere presence of one closed row used to leave a partially
    closed month open forever.  The canonical closer now runs when there are
    open rows or when the month has not been calculated yet.
    """

    today = today or timezone.localdate()
    current = month_start(today)
    previous = current - timedelta(days=1)
    previous_period = month_start(previous)
    snapshots = TeacherPerformanceSnapshot.objects.filter(
        teacher__school=school,
        period=previous_period,
    )
    if snapshots.filter(is_closed=False).exists() or (
        not snapshots.exists() and _teacher_scope_for_period(school, previous_period).exists()
    ):
        close_tpi_month(
            school=school,
            period=previous_period,
            today=previous,
        )


def _snapshot_reason(snapshot: TeacherPerformanceSnapshot) -> str:
    component_rows = snapshot.components.get("components", []) if snapshot.components else []
    best = next(
        (
            row
            for row in sorted(
                component_rows,
                key=lambda row: row.get("score") or 0,
                reverse=True,
            )
            if row.get("available")
        ),
        None,
    )
    return best["summary"] if best else "تغطية أدلة قيد الاكتمال."


def management_tpi_snapshot_context(*, school, today: date | None = None) -> dict:
    """Read the current monthly ranking without recalculating or writing.

    Page rendering must remain a read-only operation.  The expensive canonical
    refresh is still available through ``management_tpi_context`` and is called
    explicitly by the management action on the teachers dashboard.
    """
    today = today or timezone.localdate()
    period = month_start(today)
    if school is None:
        return {"period": period, "top_teachers": []}
    snapshots = list(
        TeacherPerformanceSnapshot.objects.filter(
            teacher__school=school,
            period=period,
            rank__isnull=False,
        )
        .select_related("teacher")
        .order_by("rank", "teacher__full_name")[:3]
    )
    for item in snapshots:
        item.tpi_reason = _snapshot_reason(item)
    return {"period": period, "top_teachers": snapshots}


def teacher_tpi_snapshot_context(teacher: Teacher, *, today: date | None = None) -> dict:
    """Read one teacher's current snapshot and the current leader, without writes."""
    today = today or timezone.localdate()
    period = month_start(today)
    rows = list(
        TeacherPerformanceSnapshot.objects.filter(
            teacher__school=teacher.school,
            period=period,
        )
        .filter(Q(teacher=teacher) | Q(rank=1))
        .select_related("teacher")
        .order_by("rank", "teacher__full_name")
    )
    snapshot = next((item for item in rows if item.teacher_id == teacher.pk), None)
    leader = next((item for item in rows if item.rank == 1), None)
    return {
        "snapshot": snapshot,
        "period": period,
        "leader": leader,
        "is_leader": bool(snapshot and snapshot.rank == 1),
    }


def teacher_tpi_context(teacher: Teacher, *, today: date | None = None) -> dict:
    today = today or timezone.localdate()
    close_previous_month_if_needed(school=teacher.school, today=today)
    period = month_start(today)
    snapshots = refresh_school_open_tpi(school=teacher.school, period=period, today=today)
    snapshot = next((item for item in snapshots if item.teacher_id == teacher.pk), None)
    leader = next((item for item in snapshots if item.rank == 1), None)
    return {
        "snapshot": snapshot,
        "period": period,
        "leader": leader,
        "is_leader": bool(snapshot and snapshot.rank == 1),
    }


def management_tpi_context(*, school, today: date | None = None) -> dict:
    today = today or timezone.localdate()
    close_previous_month_if_needed(school=school, today=today)
    period = month_start(today)
    snapshots = refresh_school_open_tpi(school=school, period=period, today=today)
    top = [item for item in snapshots if item.rank][:3]
    for item in top:
        item.tpi_reason = _snapshot_reason(item)
    return {"period": period, "top_teachers": top}
