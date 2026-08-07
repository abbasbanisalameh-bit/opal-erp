from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import TeacherMonthlyEvaluation


CONFIDENCE_WEIGHT = 10
MIN_TOP_RESPONSES = 5


def teachers_for_family_students(students):
    """Return the one official teacher list for a family's active students.

    The same assignment-based scope is used by the visible parent page and by
    the mandatory monthly evaluation prompt, so a teacher cannot appear in one
    path but not the other.
    """
    from academics.models import Enrollment
    from teachers.models import TeacherAssignment

    enrollments = list(Enrollment.objects.filter(
        student__in=students, status="active", section__isnull=False
    ).select_related("student", "section", "section__grade", "academic_year"))
    scope = None
    for enrollment in enrollments:
        row_scope = Q(academic_year_id=enrollment.academic_year_id, section_id=enrollment.section_id)
        scope = row_scope if scope is None else scope | row_scope
    if scope is None:
        return []
    assignments = TeacherAssignment.objects.filter(
        scope, is_active=True, teacher__is_active=True
    ).select_related("teacher", "section", "subject", "academic_year").order_by(
        "teacher__full_name", "subject__name"
    )
    enrollment_by_scope = {}
    for enrollment in enrollments:
        enrollment_by_scope.setdefault((enrollment.academic_year_id, enrollment.section_id), []).append(enrollment.student)
    rows = {}
    for assignment in assignments:
        row = rows.setdefault(assignment.teacher_id, {
            "teacher": assignment.teacher, "students": set(), "subjects": set(), "subject_objects": {},
        })
        row["students"].update(enrollment_by_scope.get((assignment.academic_year_id, assignment.section_id), []))
        row["subjects"].add(assignment.subject.name)
        row["subject_objects"][assignment.subject_id] = assignment.subject
    result = list(rows.values())
    for row in result:
        row["students"] = sorted(row["students"], key=lambda item: item.full_name)
        row["subjects"] = sorted(row["subjects"])
        row["subject_objects"] = sorted(row["subject_objects"].values(), key=lambda item: item.name)
    return result


def monthly_teacher_evaluation_snapshot(today=None, school=None):
    """Management aggregate using a Bayesian adjusted mean for fair ranking."""
    today = today or timezone.localdate()
    period = today.replace(day=1)
    qs = TeacherMonthlyEvaluation.objects.filter(period=period)
    if school is not None:
        qs = qs.filter(teacher__school=school, teacher__is_active=True)
    raw = list(qs.values("teacher_id").annotate(
        average=Avg("teaching_quality_rating"),
        responses=Count("family_id", distinct=True),
    ))
    if not raw:
        return {
            "teacher_evaluation_period": period,
            "teacher_evaluation_total": 0,
            "teacher_evaluation_average": 0,
            "top_teacher_evaluations": [],
            "teacher_evaluation_chart_labels": [],
            "teacher_evaluation_chart_values": [],
        }

    from teachers.models import Teacher

    total_responses = sum(item["responses"] for item in raw)
    global_average = (
        sum(float(item["average"] or 0) * item["responses"] for item in raw) / total_responses
        if total_responses else 0
    )
    teachers = Teacher.objects.in_bulk([row["teacher_id"] for row in raw])
    rows = []
    for item in raw:
        teacher = teachers.get(item["teacher_id"])
        if teacher is None:
            continue
        average = round(float(item["average"] or 0), 2)
        responses = int(item["responses"] or 0)
        adjusted = round(
            (responses / (responses + CONFIDENCE_WEIGHT)) * average
            + (CONFIDENCE_WEIGHT / (responses + CONFIDENCE_WEIGHT)) * global_average,
            2,
        )
        rows.append({
            "teacher": teacher,
            "teaching_average": average,
            "electronic_average": average,
            "average": average,
            "adjusted_average": adjusted,
            "responses": responses,
            "eligible_for_top": responses >= MIN_TOP_RESPONSES,
        })

    rows.sort(key=lambda row: (-row["adjusted_average"], -row["responses"], row["teacher"].full_name))
    eligible = [row for row in rows if row["eligible_for_top"]]
    chart_rows = rows[:10]
    return {
        "teacher_evaluation_period": period,
        "teacher_evaluation_total": total_responses,
        "teacher_evaluation_average": round(global_average, 2),
        "top_teacher_evaluations": eligible[:3],
        "teacher_evaluation_chart_labels": [row["teacher"].full_name for row in chart_rows],
        "teacher_evaluation_chart_values": [row["adjusted_average"] for row in chart_rows],
    }
