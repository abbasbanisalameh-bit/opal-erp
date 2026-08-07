"""Official normalized exam analytics shared by management and guardians."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from academics.models import Enrollment, Grade

from .models import StudentMark

MANAGEMENT_OFFICIAL_STATUSES = ("approved", "published", "closed")
GUARDIAN_OFFICIAL_STATUSES = ("published", "closed")
TWOPLACES = Decimal("0.01")


def _percentage(mark, maximum):
    maximum = Decimal(maximum or 0)
    return (Decimal(mark or 0) * Decimal("100") / maximum).quantize(TWOPLACES, rounding=ROUND_HALF_UP) if maximum else Decimal("0.00")


def normalized_mark_rows(queryset):
    return [
        {
            "student_id": row[0],
            "percentage": _percentage(row[1], row[2]),
            "grade_id": row[3],
            "section_id": row[4],
        }
        for row in queryset.values_list("student_id", "mark", "exam__max_mark", "exam__grade_id", "exam__section_id")
    ]


def student_rankings(*, academic_year, section=None, grade=None, guardian=False):
    statuses = GUARDIAN_OFFICIAL_STATUSES if guardian else MANAGEMENT_OFFICIAL_STATUSES
    enrollments = Enrollment.objects.filter(academic_year=academic_year, status="active")
    if section is not None:
        enrollments = enrollments.filter(section=section)
    if grade is not None:
        enrollments = enrollments.filter(grade=grade)
    enrollments = list(enrollments.select_related("student", "grade", "section").order_by("student__full_name"))
    by_student = {item.student_id: {"sum": Decimal("0"), "count": 0, "enrollment": item} for item in enrollments}
    marks = StudentMark.objects.filter(
        student_id__in=by_student,
        exam__academic_year=academic_year,
        exam__status__in=statuses,
        exam__is_active=True,
    )
    for row in normalized_mark_rows(marks):
        bucket = by_student.get(row["student_id"])
        if bucket is not None:
            bucket["sum"] += row["percentage"]
            bucket["count"] += 1
    rows = []
    for bucket in by_student.values():
        if not bucket["count"]:
            continue
        average = (bucket["sum"] / bucket["count"]).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        rows.append({
            "student": bucket["enrollment"].student,
            "enrollment": bucket["enrollment"],
            "average": average,
            "exam_count": bucket["count"],
        })
    rows.sort(key=lambda row: (-row["average"], -row["exam_count"], row["student"].full_name))
    rank = 0
    previous_key = None
    for index, row in enumerate(rows, start=1):
        key = (row["average"], row["exam_count"])
        if key != previous_key:
            rank = index
            previous_key = key
        row["rank"] = rank
    return rows


def top_students_by_grade(*, academic_year, rank_limit=3):
    """Return the first ranks independently inside every grade, including ties."""
    grades = (
        Grade.objects.filter(
            enrollments__academic_year=academic_year,
            enrollments__status="active",
        )
        .distinct()
        .order_by("order", "name")
    )
    results = []
    for grade in grades:
        grade_rows = student_rankings(academic_year=academic_year, grade=grade)
        winners = [row for row in grade_rows if row["rank"] <= rank_limit]
        if winners:
            results.append({"grade": grade, "students": winners})
    return results


def student_class_rank(student):
    enrollment = Enrollment.objects.filter(student=student, status="active").select_related(
        "academic_year", "grade", "section"
    ).order_by("-academic_year__start_date", "-pk").first()
    if not enrollment or not enrollment.section_id:
        return {"available": False, "rank": None, "average": Decimal("0"), "exam_count": 0, "class_count": 0, "enrollment": enrollment}
    rankings = student_rankings(academic_year=enrollment.academic_year, section=enrollment.section, guardian=True)
    current = next((row for row in rankings if row["student"].pk == student.pk), None)
    return {
        "available": current is not None,
        "rank": current["rank"] if current else None,
        "average": current["average"] if current else Decimal("0"),
        "total": current["average"] if current else Decimal("0"),
        "exam_count": current["exam_count"] if current else 0,
        "class_count": len(rankings),
        "enrollment": enrollment,
    }
