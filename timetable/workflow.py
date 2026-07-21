"""Unified timetable workflow entry points for OPAL ERP.

This module centralises read/query orchestration for the existing timetable
features without changing models, templates, routes, or business rules.
"""
from django.db.models import Q
from django.utils import timezone

from academics.models import Grade, Section, Subject
from core.models import AcademicYear
from teachers.models import Teacher

from admissions.services import active_school

from .live_services import DAY_CODES, management_live_status
from .models import ClassCoverage, SchoolDayEvent, SchoolScheduleSettings, TeacherAbsence, TimeSlot, TimetableEntry
from .services import build_smart_timetable


def build_timetable_dashboard_context(request):
    entries = TimetableEntry.objects.select_related(
        "academic_year", "section__grade", "subject", "teacher", "time_slot"
    )
    filters = {
        "academic_year": request.GET.get("academic_year", ""),
        "grade": request.GET.get("grade", ""),
        "section": request.GET.get("section", ""),
        "teacher": request.GET.get("teacher", ""),
        "subject": request.GET.get("subject", ""),
        "day": request.GET.get("day", ""),
        "q": request.GET.get("q", "").strip(),
    }
    if filters["academic_year"]:
        entries = entries.filter(academic_year_id=filters["academic_year"])
    if filters["grade"]:
        entries = entries.filter(section__grade_id=filters["grade"])
    if filters["section"]:
        entries = entries.filter(section_id=filters["section"])
    if filters["teacher"]:
        entries = entries.filter(teacher_id=filters["teacher"])
    if filters["subject"]:
        entries = entries.filter(subject_id=filters["subject"])
    if filters["day"]:
        entries = entries.filter(day=filters["day"])
    if filters["q"]:
        query = filters["q"]
        entries = entries.filter(
            Q(section__grade__name__icontains=query)
            | Q(section__name__icontains=query)
            | Q(subject__name__icontains=query)
            | Q(teacher__full_name__icontains=query)
            | Q(room__icontains=query)
        )

    school = active_school()
    return {
        "entries": entries,
        "academic_years": AcademicYear.objects.order_by("-start_date"),
        "grades": Grade.objects.order_by("order", "name"),
        "sections": Section.objects.select_related("grade").filter(is_active=True),
        "teachers": Teacher.objects.filter(is_active=True),
        "subjects": Subject.objects.filter(is_active=True).select_related("grade").order_by("grade__order", "name"),
        "days": TimetableEntry.DAYS,
        "filters": filters,
        "live_status": management_live_status(school),
        "coverage_needed": ClassCoverage.objects.filter(
            date=timezone.localdate(), status="needed"
        ).select_related("entry__section", "entry__subject", "entry__teacher", "entry__time_slot"),
    }


def build_smart_builder_state(request):
    school = active_school()
    years = AcademicYear.objects.filter(school=school, is_closed=False).order_by("-is_current", "-start_date")
    year_id = request.POST.get("academic_year") or request.GET.get("academic_year")
    year = years.filter(pk=year_id).first() if year_id else years.first()
    result = None
    apply = False
    if year:
        apply = request.method == "POST" and request.POST.get("action") == "apply"
        replace = request.POST.get("replace_generated") == "1"
        result = build_smart_timetable(academic_year=year, apply=apply, replace_generated=replace)
    return {"years": years, "year": year, "result": result, "apply": apply}


def build_schedule_settings_context(*, school, settings_form, event_form):
    return {
        "settings_form": settings_form,
        "event_form": event_form,
        "events": SchoolDayEvent.objects.filter(school=school),
    }


def create_absence_coverages(absence, school):
    day = DAY_CODES[absence.date.weekday()]
    entries = TimetableEntry.objects.filter(
        teacher=absence.teacher,
        day=day,
        academic_year__school=school,
        academic_year__is_current=True,
        is_active=True,
    )
    for entry in entries:
        ClassCoverage.objects.get_or_create(entry=entry, date=absence.date)


def upcoming_coverages_queryset():
    return ClassCoverage.objects.filter(date__gte=timezone.localdate()).select_related(
        "entry__teacher", "entry__section", "entry__subject", "entry__time_slot", "substitute_teacher"
    ).order_by("date", "entry__time_slot__order")


def substitute_teacher_is_unavailable(*, coverage, substitute):
    busy = TimetableEntry.objects.filter(
        teacher=substitute,
        academic_year=coverage.entry.academic_year,
        day=coverage.entry.day,
        time_slot=coverage.entry.time_slot,
        is_active=True,
    ).exists()
    absent = TeacherAbsence.objects.filter(teacher=substitute, date=coverage.date).exists()
    return busy or absent


def build_print_context(entries, title):
    return {
        "title": title,
        "days": [(label, entries.filter(day=code)) for code, label in TimetableEntry.DAYS],
    }


def section_schedule_queryset(section):
    return TimetableEntry.objects.filter(section=section, is_active=True).select_related(
        "subject", "teacher", "time_slot"
    )


def teacher_schedule_queryset(teacher):
    return TimetableEntry.objects.filter(teacher=teacher, is_active=True).select_related(
        "section__grade", "subject", "time_slot"
    )


def active_time_slots_queryset():
    return TimeSlot.objects.all()


def school_schedule_settings(school):
    return SchoolScheduleSettings.objects.get_or_create(school=school)[0]
