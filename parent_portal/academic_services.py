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
    from exams.analytics import student_class_rank as official_student_class_rank

    return official_student_class_rank(student)


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
