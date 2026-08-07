"""Teacher workload calculations from the single annual Subject plan."""
from collections import defaultdict

from academics.models import Subject
from core.models import AcademicYear
from timetable.models import TimetableEntry


def current_year_for_teacher(teacher):
    return (
        AcademicYear.objects.filter(school=teacher.school, is_closed=False)
        .order_by("-is_current", "-start_date")
        .first()
    )


def annual_subject_plan_map(academic_year):
    """Return weekly periods from the single annual Subject plan."""
    return {
        (item.grade_id, item.pk): item.weekly_periods
        for item in Subject.objects.filter(
            academic_year=academic_year,
            is_active=True,
        ).only("id", "grade_id", "weekly_periods")
    }


def teacher_workload_summary(teacher, academic_year=None):
    academic_year = academic_year or current_year_for_teacher(teacher)
    if not academic_year:
        return {
            "academic_year": None, "assigned": 0, "scheduled": 0,
            "load": teacher.weekly_teaching_load, "remaining": teacher.weekly_teaching_load,
            "missing_plan": 0, "status": "لا يوجد عام دراسي مفتوح",
            "status_code": "unavailable", "free_label": teacher.get_free_period_policy_display(),
        }

    assignments = list(
        teacher.assignments.filter(academic_year=academic_year, is_active=True)
        .select_related("section__grade", "subject")
    )
    assigned = sum(item.subject.weekly_periods for item in assignments)
    missing_plan = sum(
        1 for item in assignments
        if item.subject.academic_year_id != academic_year.pk or item.subject.grade_id != item.section.grade_id
    )
    scheduled = TimetableEntry.objects.filter(
        teacher=teacher, academic_year=academic_year, is_active=True,
    ).count()
    load = teacher.weekly_teaching_load
    remaining = None if load is None else load - assigned
    if load is None:
        status, status_code = "النصاب غير مضبوط", "missing"
    elif assigned > load:
        status, status_code = "متجاوز", "danger"
    elif assigned == load:
        status, status_code = "مكتمل", "success"
    else:
        status, status_code = "ضمن النصاب", "primary"
    if missing_plan:
        status = f"{status} · {missing_plan} تكليف غير متطابق مع خطة العام"
        status_code = "warning" if status_code != "danger" else status_code

    if teacher.free_period_policy == "daily":
        free_label = f"{teacher.daily_free_periods} يوميًا"
    elif teacher.free_period_policy == "weekly":
        free_label = f"{teacher.weekly_free_periods} أسبوعيًا"
    else:
        free_label = "تلقائي حسب المتاح"

    return {
        "academic_year": academic_year, "assigned": assigned, "scheduled": scheduled,
        "load": load, "remaining": remaining, "missing_plan": missing_plan,
        "status": status, "status_code": status_code, "free_label": free_label,
        "assignments": assignments,
    }


def workload_by_teacher(assignments, plan_map=None):
    totals = defaultdict(int)
    missing = defaultdict(int)
    for assignment in assignments:
        subject = assignment.subject
        if subject.academic_year_id != assignment.academic_year_id or subject.grade_id != assignment.section.grade_id:
            missing[assignment.teacher_id] += 1
            continue
        totals[assignment.teacher_id] += subject.weekly_periods
    return totals, missing
