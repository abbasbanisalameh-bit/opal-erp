"""OPAL exams and grades workflow entry points.

This module centralises the read-side orchestration for exams, gradebooks,
student records and report cards without changing the existing models,
permissions, templates or calculations.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Value

from academics.models import Enrollment, Grade, Section, Subject
from core.models import AcademicYear, Semester
from students.models import Student
from teachers.models import Teacher, TeacherAssignment

from .mark_entry_service import build_mark_rows, resolve_mark_entry_scope, save_exam_marks
from .models import Exam, StudentMark
from .services import annual_report, dashboard_statistics, exam_statistics, student_academic_record


def current_scope():
    year = AcademicYear.objects.filter(is_current=True, is_closed=False).first()
    if year is None:
        year = AcademicYear.objects.filter(is_closed=False).order_by("-start_date").first()
    semester = None
    if year:
        semester = year.semesters.filter(is_current=True).first() or year.semesters.order_by("code").first()
    return year, semester


def selected_scope(request):
    current_year, _ = current_scope()
    year_id = request.GET.get("academic_year") or (str(current_year.pk) if current_year else "")
    year = AcademicYear.objects.filter(pk=year_id).first() if year_id else None
    semester_id = request.GET.get("semester")
    if not semester_id and year:
        default_semester = year.semesters.filter(is_current=True).first() or year.semesters.order_by("code").first()
        semester_id = str(default_semester.pk) if default_semester else ""
    semester = Semester.objects.filter(pk=semester_id, academic_year=year).first() if semester_id and year else None
    return {
        "year": year,
        "semester": semester,
        "year_id": str(year.pk) if year else "",
        "semester_id": str(semester.pk) if semester else "",
        "grade_id": request.GET.get("grade", ""),
        "section_id": request.GET.get("section", ""),
        "subject_id": request.GET.get("subject", ""),
        "teacher_id": request.GET.get("teacher", ""),
    }


def scope_filter_context(scope):
    year = scope["year"]
    grade_id = scope["grade_id"]
    sections = Section.objects.filter(is_active=True).select_related("grade", "academic_year")
    grades = Grade.objects.filter(is_active=True)
    subjects = Subject.objects.filter(is_active=True).select_related("grade")
    teachers = Teacher.objects.filter(is_active=True)
    if year:
        grades = grades.filter(school=year.school)
        sections = sections.filter(academic_year=year)
        teachers = teachers.filter(school=year.school)
    if grade_id:
        sections = sections.filter(grade_id=grade_id)
        subjects = subjects.filter(grade_id=grade_id)
    else:
        subjects = subjects.none()
    return {
        "academic_years": AcademicYear.objects.all().order_by("-start_date"),
        "semesters": year.semesters.all().order_by("code") if year else Semester.objects.none(),
        "grades": grades.order_by("order", "name"),
        "sections": sections.order_by("grade__order", "name"),
        "subjects": subjects.order_by("name"),
        "teachers": teachers.order_by("full_name"),
        "filters": scope,
    }


def gradebook_rows(scope):
    year, semester = scope["year"], scope["semester"]
    section_id, subject_id = scope["section_id"], scope["subject_id"]
    if not all([year, semester, section_id, subject_id]):
        return [], {}, None
    section = Section.objects.filter(pk=section_id, academic_year=year, is_active=True).select_related("grade").first()
    subject = Subject.objects.filter(pk=subject_id, grade=section.grade if section else None, is_active=True).first()
    if not section or not subject:
        return [], {}, None
    assignment = TeacherAssignment.objects.filter(
        academic_year=year, section=section, subject=subject, is_active=True, teacher__is_active=True
    ).select_related("teacher", "section", "subject").first()
    exams = {
        item.exam_type: item
        for item in Exam.objects.filter(
            academic_year=year, semester=semester, section=section, subject=subject, is_active=True,
        ).select_related("teacher_assignment__teacher")
    }
    enrollments = Enrollment.objects.filter(
        academic_year=year, section=section, status="active"
    ).select_related("student").order_by("student__full_name")
    students = [item.student for item in enrollments]
    marks = defaultdict(dict)
    for item in StudentMark.objects.filter(
        exam_id__in=[exam.pk for exam in exams.values()], student__in=students
    ).select_related("exam"):
        marks[item.student_id][item.exam.exam_type] = item
    rows = []
    for student in students:
        cells = []
        total = Decimal("0.00")
        for exam_type, label in Exam.EXAM_TYPES:
            exam = exams.get(exam_type)
            mark = marks[student.pk].get(exam_type)
            value = Decimal(mark.mark) if mark else None
            if value is not None:
                total += value
            cells.append({"type": exam_type, "label": label, "exam": exam, "mark": mark, "value": value})
        rows.append({"student": student, "cells": cells, "total": total})
    return rows, exams, assignment


def build_gradebook_context(request):
    scope = selected_scope(request)
    rows, exams, assignment = gradebook_rows(scope)
    context = scope_filter_context(scope)
    context.update({
        "rows": rows,
        "assessment_exams": exams,
        "assignment": assignment,
        "pending_count": Exam.objects.filter(status="submitted").count(),
        "scope_complete": bool(rows or all([scope["year"], scope["semester"], scope["section_id"], scope["subject_id"]])),
    })
    return context


def _filtered_exams(scope):
    exams = Exam.objects.select_related(
        "academic_year", "semester", "grade", "section", "subject", "teacher_assignment__teacher"
    )
    if scope["year"]:
        exams = exams.filter(academic_year=scope["year"])
    if scope["semester"]:
        exams = exams.filter(semester=scope["semester"])
    for key in ("grade", "section", "subject"):
        value = scope[f"{key}_id"]
        if value:
            exams = exams.filter(**{f"{key}_id": value})
    return exams


def build_exam_definitions_context(request):
    scope = selected_scope(request)
    context = scope_filter_context(scope)
    context["exams"] = _filtered_exams(scope).order_by("grade__order", "section__name", "subject__name", "exam_type")
    return context


def build_exam_dashboard_context(request):
    scope = selected_scope(request)
    exams = _filtered_exams(scope)
    if scope["teacher_id"]:
        exams = exams.filter(teacher_assignment__teacher_id=scope["teacher_id"])
    exams = exams.order_by("-exam_date", "name")
    stats = dashboard_statistics(exams)
    recent_exams = list(exams[:15])
    for exam in recent_exams:
        exam.analytics = exam_statistics(exam)
    normalized = ExpressionWrapper(
        F("mark") * Value(Decimal("100.00")) / F("exam__max_mark"),
        output_field=DecimalField(max_digits=7, decimal_places=2),
    )
    performance_qs = StudentMark.objects.filter(exam__in=exams).exclude(exam__teacher_assignment=None).annotate(
        normalized=normalized
    ).values(
        "exam__teacher_assignment__teacher_id", "exam__teacher_assignment__teacher__full_name",
        "exam__subject__name", "exam__section__name", "exam__grade__name",
    ).annotate(average=Avg("normalized"), results=Count("id")).order_by("-average")
    performance = []
    for row in performance_qs:
        avg = Decimal(row["average"] or 0)
        row["classification"] = "ممتاز" if avg >= 90 else "جيد جدًا" if avg >= 80 else "جيد" if avg >= 70 else "مقبول" if avg >= 60 else "بحاجة متابعة"
        performance.append(row)
    context = scope_filter_context(scope)
    context.update({"stats": stats, "recent_exams": recent_exams, "teacher_performance": performance})
    return context


def build_scope_options_payload(*, year_id=None, grade_id=None, section_id=None, subject_id=None):
    semesters = Semester.objects.filter(academic_year_id=year_id).order_by("code") if year_id else Semester.objects.none()
    sections = Section.objects.filter(academic_year_id=year_id, grade_id=grade_id, is_active=True).order_by("name") if year_id and grade_id else Section.objects.none()
    subjects = Subject.objects.filter(grade_id=grade_id, is_active=True).order_by("name") if grade_id else Subject.objects.none()
    assignment = None
    if year_id and section_id and subject_id:
        assignment = TeacherAssignment.objects.filter(
            academic_year_id=year_id, section_id=section_id, subject_id=subject_id,
            is_active=True, teacher__is_active=True,
        ).select_related("teacher").first()
    return {
        "semesters": [{"id": item.pk, "label": item.get_code_display(), "current": item.is_current} for item in semesters],
        "sections": [{"id": item.pk, "label": str(item)} for item in sections],
        "subjects": [{"id": item.pk, "label": item.name} for item in subjects],
        "teacher": {"id": assignment.teacher_id, "name": assignment.teacher.full_name} if assignment else None,
    }


def build_mark_list_queryset():
    return StudentMark.objects.select_related("student", "exam", "exam__subject", "exam__section").all()


def build_exam_detail_context(exam):
    analytics = exam_statistics(exam)
    return {"exam": exam, "marks": analytics.pop("marks"), "stats": analytics}


def build_student_record_context(student, *, published_only=False):
    return {"student": student, "record": student_academic_record(student, published_only=published_only)}


def resolve_report_year(student, year_id=None):
    if year_id:
        return AcademicYear.objects.filter(pk=year_id).first()
    enrollment = student.enrollments.select_related("academic_year").order_by("-academic_year__start_date").first()
    return enrollment.academic_year if enrollment else AcademicYear.objects.filter(is_current=True, is_closed=False).first()


def build_student_report_card_context(student, *, year_id=None):
    academic_year = resolve_report_year(student, year_id)
    report = annual_report(student=student, academic_year=academic_year) if academic_year else None
    return {"student": student, "report": report}


__all__ = [
    "build_exam_dashboard_context", "build_exam_definitions_context", "build_exam_detail_context",
    "build_gradebook_context", "build_mark_list_queryset", "build_mark_rows",
    "build_scope_options_payload", "build_student_record_context", "build_student_report_card_context",
    "resolve_mark_entry_scope", "resolve_report_year", "save_exam_marks",
]
