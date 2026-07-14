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
    marks_qs = StudentMark.objects.filter(exam_id__in=[e.id for e in exams])
    aggregate = marks_qs.aggregate(count=Count("id"), average=Avg("mark"), highest=Max("mark"), lowest=Min("mark"))
    passed = failed = 0
    for mark in marks_qs.select_related("exam"):
        if Decimal(str(mark.percentage)) >= mark.exam.pass_percentage: passed += 1
        else: failed += 1
    total = aggregate["count"] or 0
    return {"exam_count": len(exams), "mark_count": total, "average": aggregate["average"] or Decimal("0"), "highest": aggregate["highest"] or Decimal("0"), "lowest": aggregate["lowest"] or Decimal("0"), "passed": passed, "failed": failed, "pass_rate": round((passed / total) * 100, 2) if total else 0}


def student_academic_record(student, published_only=False) -> dict:
    marks_qs = StudentMark.objects.filter(student=student)
    if published_only:
        marks_qs = marks_qs.filter(exam__status="published")
    marks = list(marks_qs.select_related("exam", "exam__subject", "exam__grade", "exam__academic_year").order_by("exam__exam_date", "exam__subject__name", "exam__name"))
    by_subject = defaultdict(lambda: {"marks": [], "total_percentage": Decimal("0")})
    by_year = defaultdict(lambda: {"marks": [], "total": Decimal("0")})
    timeline = []
    for item in marks:
        pct = Decimal(str(item.percentage))
        subject_name = str(item.exam.subject)
        year_name = str(item.exam.academic_year)
        by_subject[subject_name]["marks"].append(item)
        by_subject[subject_name]["total_percentage"] += pct
        by_year[year_name]["marks"].append(item)
        by_year[year_name]["total"] += pct
        timeline.append({"label": item.exam.name, "subject": subject_name, "date": item.exam.exam_date, "percentage": pct})

    subjects = []
    for name, data in by_subject.items():
        count = len(data["marks"])
        avg = (data["total_percentage"] / count) if count else Decimal("0")
        percentages = [Decimal(str(m.percentage)) for m in data["marks"]]
        subjects.append({"name": name, "count": count, "average": avg.quantize(Decimal("0.01")), "highest": max(percentages) if percentages else Decimal("0"), "lowest": min(percentages) if percentages else Decimal("0"), "trend": (percentages[-1] - percentages[0]).quantize(Decimal("0.01")) if len(percentages) > 1 else Decimal("0"), "grade": _grade_label(avg), "marks": data["marks"]})
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
