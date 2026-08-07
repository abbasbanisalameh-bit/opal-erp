from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Iterable

from django.db.models import Avg, Count, Max, Min

from .models import Exam, StudentMark



def _grade_label(value: Decimal) -> str:
    if value >= 90:
        return "ممتاز"
    if value >= 80:
        return "جيد جداً"
    if value >= 70:
        return "جيد"
    if value >= 60:
        return "مقبول"
    return "يحتاج متابعة"


def exam_statistics(exam: Exam) -> dict:
    marks = list(StudentMark.objects.filter(exam=exam).select_related("student").order_by("-mark", "student__full_name"))
    values = [Decimal(m.mark) for m in marks]
    max_mark = Decimal(exam.max_mark or 0)
    distribution = {"excellent": 0, "very_good": 0, "good": 0, "pass": 0, "failed": 0}
    passed = failed = 0
    for mark in marks:
        p = Decimal(str(mark.percentage))
        passed += int(p >= exam.pass_percentage)
        failed += int(p < exam.pass_percentage)
        key = "excellent" if p >= 90 else "very_good" if p >= 80 else "good" if p >= 70 else "pass" if p >= exam.pass_percentage else "failed"
        distribution[key] += 1
    total = len(values)
    average = (sum(values, Decimal("0")) / total) if total else Decimal("0")
    avg_pct = (average / max_mark * Decimal("100")) if total and max_mark else Decimal("0")
    return {"marks": marks, "count": total, "highest": max(values) if values else Decimal("0"), "lowest": min(values) if values else Decimal("0"), "average": average.quantize(Decimal("0.01")), "average_percentage": avg_pct.quantize(Decimal("0.01")), "passed": passed, "failed": failed, "pass_rate": round((passed / total) * 100, 2) if total else 0, "distribution": distribution}


def dashboard_statistics(exams: Iterable[Exam]) -> dict:
    exams = list(exams)
    marks = list(StudentMark.objects.filter(exam_id__in=[e.id for e in exams]).select_related("exam"))
    percentages = [Decimal(str(mark.percentage)) for mark in marks]
    passed = sum(1 for mark in marks if Decimal(str(mark.percentage)) >= mark.exam.pass_percentage)
    failed = len(marks) - passed
    total = len(marks)
    average = (sum(percentages, Decimal("0")) / total).quantize(Decimal("0.01")) if total else Decimal("0.00")
    return {
        "exam_count": len(exams), "mark_count": total,
        "average": average,
        "highest": max(percentages) if percentages else Decimal("0.00"),
        "lowest": min(percentages) if percentages else Decimal("0.00"),
        "passed": passed, "failed": failed,
        "pass_rate": round((passed / total) * 100, 2) if total else 0,
    }


def student_academic_record(student, published_only=False) -> dict:
    marks_qs = StudentMark.objects.filter(student=student)
    if published_only:
        marks_qs = marks_qs.filter(exam__status__in=["published", "closed"])
    marks = list(marks_qs.select_related("exam", "exam__subject", "exam__grade", "exam__academic_year").order_by("exam__exam_date", "exam__subject__name", "exam__name"))
    by_subject = defaultdict(lambda: {"marks": [], "total_percentage": Decimal("0"), "color": "#64748B"})
    by_year = defaultdict(lambda: {"marks": [], "total": Decimal("0")})
    timeline = []
    for item in marks:
        pct = Decimal(str(item.percentage))
        subject_name = str(item.exam.subject)
        year_name = str(item.exam.academic_year)
        by_subject[subject_name]["marks"].append(item)
        by_subject[subject_name]["total_percentage"] += pct
        by_subject[subject_name]["color"] = item.exam.subject.color or "#64748B"
        by_year[year_name]["marks"].append(item)
        by_year[year_name]["total"] += pct
        timeline.append({"label": item.exam.name, "subject": subject_name, "date": item.exam.exam_date, "percentage": pct})

    subjects = []
    for name, data in by_subject.items():
        count = len(data["marks"])
        avg = (data["total_percentage"] / count) if count else Decimal("0")
        percentages = [Decimal(str(m.percentage)) for m in data["marks"]]
        subjects.append({"name": name, "color": data["color"], "count": count, "average": avg.quantize(Decimal("0.01")), "highest": max(percentages) if percentages else Decimal("0"), "lowest": min(percentages) if percentages else Decimal("0"), "trend": (percentages[-1] - percentages[0]).quantize(Decimal("0.01")) if len(percentages) > 1 else Decimal("0"), "grade": _grade_label(avg), "marks": data["marks"]})
    subjects.sort(key=lambda r: (-r["average"], r["name"]))

    years = []
    for name, data in by_year.items():
        count = len(data["marks"])
        avg = data["total"] / count if count else Decimal("0")
        years.append({"name": name, "count": count, "average": avg.quantize(Decimal("0.01")), "grade": _grade_label(avg)})

    overall = sum((Decimal(str(m.percentage)) for m in marks), Decimal("0")) / len(marks) if marks else Decimal("0")
    passed = sum(1 for m in marks if Decimal(str(m.percentage)) >= m.exam.pass_percentage)
    strengths = [s for s in subjects if s["average"] >= 80][:5]
    needs_support = [s for s in reversed(subjects) if s["average"] < 60][:5]
    return {"marks": list(reversed(marks)), "subjects": subjects, "years": years, "timeline": list(reversed(timeline)), "exam_count": len(marks), "overall_average": overall.quantize(Decimal("0.01")), "overall_grade": _grade_label(overall), "passed": passed, "failed": len(marks)-passed, "pass_rate": round((passed/len(marks))*100,2) if marks else 0, "strengths": strengths, "needs_support": needs_support}

# ---------------------------------------------------------------------------
# Official OPAL report calculations: four assessments per subject/semester.
# ---------------------------------------------------------------------------
TWOPLACES = Decimal("0.01")
ASSESSMENT_ORDER = ("first", "second", "third", "final")


def _two_places(value):
    return Decimal(value or 0).quantize(TWOPLACES)


def subject_semester_result(*, student, academic_year, semester, subject):
    marks = {
        row.exam.exam_type: row
        for row in StudentMark.objects.filter(
            student=student,
            exam__academic_year=academic_year,
            exam__semester=semester,
            exam__subject=subject,
            exam__is_active=True,
            exam__status__in=["published", "closed"],
        ).select_related("exam")
    }
    assessments = []
    total = Decimal("0.00")
    complete = True
    for exam_type in ASSESSMENT_ORDER:
        row = marks.get(exam_type)
        maximum = Exam.MAX_MARKS[exam_type]
        mark = _two_places(row.mark if row else 0)
        if row is None:
            complete = False
        total += mark
        assessments.append({
            "exam_type": exam_type,
            "label": dict(Exam.EXAM_TYPES)[exam_type],
            "mark": mark,
            "max_mark": maximum,
        })
    return {
        "subject": subject,
        "assessments": assessments,
        "total": _two_places(total),
        "max_total": Decimal("100.00"),
        "complete": complete,
    }


def semester_report(*, student, academic_year, semester):
    from academics.models import Subject

    enrollment = student.enrollments.filter(academic_year=academic_year).select_related("grade").first()
    if enrollment:
        subjects = list(Subject.objects.filter(academic_year=academic_year, grade=enrollment.grade, is_active=True).order_by("name"))
    else:
        subjects = list(Subject.objects.filter(
            exams__marks__student=student,
            exams__academic_year=academic_year,
            exams__semester=semester,
        ).distinct().order_by("name"))
    rows = [
        subject_semester_result(
            student=student,
            academic_year=academic_year,
            semester=semester,
            subject=subject,
        )
        for subject in subjects
    ]
    average = _two_places(sum((row["total"] for row in rows), Decimal("0.00")) / len(rows)) if rows else Decimal("0.00")
    return {
        "semester": semester,
        "rows": rows,
        "subject_count": len(rows),
        "average": average,
        "complete": bool(rows) and all(row["complete"] for row in rows),
    }


def annual_report(*, student, academic_year):
    academic_year.ensure_semesters()
    first = academic_year.semesters.get(code="first")
    second = academic_year.semesters.get(code="second")
    first_report = semester_report(student=student, academic_year=academic_year, semester=first)
    second_report = semester_report(student=student, academic_year=academic_year, semester=second)
    from .models import AnnualStudentResult

    snapshot = AnnualStudentResult.objects.filter(student=student, academic_year=academic_year).first()
    annual_average = snapshot.general_average if snapshot else _two_places((first_report["average"] + second_report["average"]) / Decimal("2"))
    return {
        "student": student,
        "academic_year": academic_year,
        "first": first_report,
        "second": second_report,
        "terms": [first_report, second_report],
        "annual_average": annual_average,
        "complete": bool(snapshot) or (first_report["complete"] and second_report["complete"]),
        "is_snapshot": bool(snapshot),
    }


def student_marks_matrix(student, academic_year=None):
    """Compact read-only matrix for guardian and management enquiries."""
    from academics.models import Enrollment, Subject
    from core.models import AcademicYear

    if academic_year is None:
        enrollment = student.enrollments.select_related("academic_year", "grade").filter(status="active").order_by("-academic_year__start_date").first()
        academic_year = enrollment.academic_year if enrollment else AcademicYear.objects.filter(is_current=True).first()
    else:
        enrollment = student.enrollments.select_related("grade").filter(academic_year=academic_year).first()

    if not academic_year:
        return {"academic_year": None, "subjects": [], "exam_types": [], "by_subject": [], "by_exam": [], "semesters": []}

    semesters = list(academic_year.semesters.order_by("code"))
    subject_qs = Subject.objects.filter(academic_year=academic_year, is_active=True)
    if enrollment:
        subject_qs = subject_qs.filter(grade=enrollment.grade)
    else:
        subject_qs = subject_qs.filter(exams__marks__student=student, exams__academic_year=academic_year).distinct()
    subjects = list(subject_qs.order_by("name"))

    marks = StudentMark.objects.filter(
        student=student,
        exam__academic_year=academic_year,
        exam__is_active=True,
        exam__status__in=["published", "closed"],
    ).select_related("exam", "exam__semester", "exam__subject")
    mark_map = {(m.exam.semester_id, m.exam.subject_id, m.exam.exam_type): m for m in marks}

    exam_types = [{"key": key, "label": label, "max_mark": Exam.MAX_MARKS[key]} for key, label in Exam.EXAM_TYPES]
    by_subject = []
    for subject in subjects:
        term_rows = []
        for semester in semesters:
            cells = []
            total = Decimal("0.00")
            for exam_type in exam_types:
                mark = mark_map.get((semester.id, subject.id, exam_type["key"]))
                if mark:
                    total += Decimal(mark.mark)
                cells.append({"exam_type": exam_type, "mark": mark, "value": mark.mark if mark else None})
            term_rows.append({"semester": semester, "cells": cells, "total": total, "is_closed": semester.is_closed})
        by_subject.append({"subject": subject, "terms": term_rows})

    by_exam = []
    for semester in semesters:
        for exam_type in exam_types:
            rows = []
            for subject in subjects:
                mark = mark_map.get((semester.id, subject.id, exam_type["key"]))
                rows.append({"subject": subject, "mark": mark, "value": mark.mark if mark else None})
            by_exam.append({"semester": semester, "exam_type": exam_type, "rows": rows})

    return {
        "academic_year": academic_year,
        "subjects": subjects,
        "exam_types": exam_types,
        "by_subject": by_subject,
        "by_exam": by_exam,
        "semesters": semesters,
    }
