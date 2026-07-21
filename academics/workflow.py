"""Unified academic workflow entry points for OPAL ERP.

This module keeps the current academic behavior intact while giving the
academic structure, catalogues, and student lifecycle a single internal
service boundary.
"""
from django.urls import reverse

from core.models import AcademicYear, School, Semester

from .models import Grade, Section, StudentLifecycleEvent, Subject


def academic_school():
    """Return the existing active school without creating parallel records."""
    return School.objects.filter(is_active=True).first() or School.objects.first()


def academic_structure_url(year_id=None, **params):
    url = reverse("academics:academic_structure")
    query = []
    if year_id:
        query.append(f"year={year_id}")
    query.extend(f"{key}={value}" for key, value in params.items() if value not in (None, ""))
    return f"{url}?{'&'.join(query)}" if query else url


def build_academic_year_list_context():
    return {
        "years": AcademicYear.objects.select_related("school").order_by("-start_date"),
    }


def build_semester_list_context():
    return {
        "semesters": Semester.objects.select_related("academic_year", "academic_year__school").order_by(
            "-academic_year__start_date", "start_date"
        ),
    }


def build_subject_list_context():
    return {
        "subjects": Subject.objects.select_related("grade", "grade__school").order_by(
            "grade__order", "name"
        ),
    }


def build_academic_catalogue_snapshot(school=None, academic_year=None):
    """Build one stable read snapshot of the current academic catalogue."""
    school = school or academic_school()
    years = AcademicYear.objects.none()
    grades = Grade.objects.none()
    sections = Section.objects.none()
    subjects = Subject.objects.none()
    if school is not None:
        years = AcademicYear.objects.filter(school=school).order_by("-is_current", "-start_date")
        academic_year = academic_year or years.filter(is_current=True).first() or years.first()
        grades = Grade.objects.filter(school=school).order_by("order", "name")
        subjects = Subject.objects.filter(grade__school=school).select_related("grade").order_by(
            "grade__order", "name"
        )
        if academic_year is not None:
            sections = Section.objects.filter(
                academic_year=academic_year,
                branch__school=school,
            ).select_related("grade", "branch", "homeroom_teacher").order_by("grade__order", "name")
    return {
        "school": school,
        "academic_year": academic_year,
        "years": years,
        "grades": grades,
        "sections": sections,
        "subjects": subjects,
    }


def build_lifecycle_list_context(action=""):
    events = StudentLifecycleEvent.objects.select_related(
        "student",
        "from_enrollment__grade",
        "to_enrollment__grade",
        "performed_by",
    )
    if action:
        events = events.filter(action=action)
    return {
        "events": events[:500],
        "actions": StudentLifecycleEvent.ACTION_CHOICES,
        "selected_action": action,
    }
