from collections import defaultdict
from decimal import Decimal

from academics.models import Enrollment
from exams.models import StudentMark
from teachers.models import Homework


def current_enrollment(student):
    return (
        Enrollment.objects.filter(student=student, status="active")
        .select_related("academic_year", "grade", "section")
        .order_by("-academic_year__start_date", "-pk")
        .first()
    )


def student_class_rank(student):
    enrollment = current_enrollment(student)
    if enrollment is None or enrollment.section_id is None:
        return {"available": False, "rank": None, "total": Decimal("0"), "class_count": 0, "enrollment": enrollment}

    student_ids = list(
        Enrollment.objects.filter(
            academic_year=enrollment.academic_year,
            section=enrollment.section,
            status="active",
        ).values_list("student_id", flat=True)
    )
    totals = {student_id: Decimal("0") for student_id in student_ids}
    for student_id, mark in StudentMark.objects.filter(
        student_id__in=student_ids,
        exam__academic_year=enrollment.academic_year,
        exam__status__in=["published", "closed"],
        exam__is_active=True,
    ).values_list("student_id", "mark"):
        totals[student_id] += Decimal(mark or 0)

    ordered_values = sorted(set(totals.values()), reverse=True)
    wanted_total = totals.get(student.pk, Decimal("0"))
    rank = ordered_values.index(wanted_total) + 1 if ordered_values else None
    has_published_marks = StudentMark.objects.filter(
        student_id__in=student_ids,
        exam__academic_year=enrollment.academic_year,
        exam__status__in=["published", "closed"],
        exam__is_active=True,
    ).exists()
    return {
        "available": has_published_marks,
        "rank": rank if has_published_marks else None,
        "total": wanted_total,
        "class_count": len(student_ids),
        "enrollment": enrollment,
    }


def homework_for_student(student):
    enrollment = current_enrollment(student)
    if enrollment is None or enrollment.section_id is None:
        return Homework.objects.none()
    return (
        Homework.objects.filter(
            assignment__academic_year=enrollment.academic_year,
            assignment__section=enrollment.section,
            assignment__is_active=True,
            is_active=True,
        )
        .select_related("assignment__subject", "assignment__teacher", "assignment__section")
        .order_by("-assigned_date", "due_date")
    )


def homework_rows_for_students(students):
    rows = []
    for student in students:
        rows.append({"student": student, "items": homework_for_student(student)})
    return rows
