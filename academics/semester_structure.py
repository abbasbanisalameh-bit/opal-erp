"""Version the canonical academic structure at term boundaries."""

from django.db import transaction

from admissions.models import GradeFee
from core.models import SemesterStructureSnapshot
from teachers.models import TeacherAssignment
from timetable.models import (
    SchoolDayEvent,
    SchoolScheduleSettings,
    TimeSlot,
    TimetableEntry,
)

from .models import Section, Subject


def build_semester_structure_payload(semester):
    year = semester.academic_year
    school = year.school
    sections = Section.objects.filter(academic_year=year).select_related(
        "branch", "grade", "homeroom_teacher"
    )
    subjects = Subject.objects.filter(academic_year=year, grade__school=school).select_related("grade", "academic_year")
    fees = GradeFee.objects.filter(academic_year=year).select_related("grade")
    assignments = TeacherAssignment.objects.filter(academic_year=year).select_related(
        "teacher", "section", "subject"
    )
    entries = TimetableEntry.objects.filter(academic_year=year).select_related(
        "section", "subject", "teacher", "time_slot"
    )
    settings = SchoolScheduleSettings.objects.filter(school=school).first()
    return {
        "schema": 2,
        "academic_year": {"id": year.pk, "name": year.name},
        "semester": {"id": semester.pk, "code": semester.code, "name": semester.name},
        "sections": [
            {
                "id": item.pk,
                "branch_id": item.branch_id,
                "grade_id": item.grade_id,
                "name": item.name,
                "capacity": item.capacity,
                "homeroom_teacher_id": item.homeroom_teacher_id,
                "is_default": item.is_default,
                "is_active": item.is_active,
            }
            for item in sections
        ],
        "subjects": [
            {
                "id": item.pk,
                "academic_year_id": item.academic_year_id,
                "grade_id": item.grade_id,
                "name": item.name,
                "code": item.code,
                "weekly_periods": item.weekly_periods,
                "is_required": item.is_required,
                "canonical_key": item.canonical_key,
                "color": item.color,
                "is_active": item.is_active,
            }
            for item in subjects
        ],
        "grade_fees": [
            {
                "id": item.pk,
                "grade_id": item.grade_id,
                "tuition_fee": str(item.tuition_fee),
                "is_active": item.is_active,
            }
            for item in fees
        ],
        "assignments": [
            {
                "id": item.pk,
                "teacher_id": item.teacher_id,
                "section_id": item.section_id,
                "subject_id": item.subject_id,
                "is_primary": item.is_primary,
                "is_active": item.is_active,
            }
            for item in assignments
        ],
        "time_slots": [
            {
                "id": item.pk,
                "name": item.name,
                "start_time": item.start_time.isoformat(),
                "end_time": item.end_time.isoformat(),
                "order": item.order,
                "is_active": item.is_active,
            }
            for item in TimeSlot.objects.all()
        ],
        "timetable": [
            {
                "id": item.pk,
                "section_id": item.section_id,
                "subject_id": item.subject_id,
                "teacher_id": item.teacher_id,
                "day": item.day,
                "time_slot_id": item.time_slot_id,
                "room": item.room,
                "generated_automatically": item.generated_automatically,
                "is_active": item.is_active,
            }
            for item in entries
        ],
        "schedule": {
            "weekend_days": settings.weekend_days if settings else "",
            "alert_minutes_before_end": settings.alert_minutes_before_end if settings else None,
            "events": [
                {
                    "id": item.pk,
                    "name": item.name,
                    "event_type": item.event_type,
                    "start_time": item.start_time.isoformat() if item.start_time else None,
                    "end_time": item.end_time.isoformat() if item.end_time else None,
                    "days": item.days,
                    "order": item.order,
                    "is_active": item.is_active,
                }
                for item in SchoolDayEvent.objects.filter(school=school)
            ],
        },
    }


@transaction.atomic
def capture_semester_structure(*, semester, user=None, final=False, source_snapshot=None, payload=None):
    snapshot, _created = SemesterStructureSnapshot.objects.select_for_update().get_or_create(
        semester=semester,
        defaults={"payload": {}},
    )
    snapshot.payload = payload if payload is not None else build_semester_structure_payload(semester)
    snapshot.source_snapshot = source_snapshot
    snapshot.is_final = final
    snapshot.captured_by = user if getattr(user, "is_authenticated", False) else None
    snapshot.save()
    return snapshot


@transaction.atomic
def finalize_and_seed_next_semester(*, semester, user=None):
    source = capture_semester_structure(semester=semester, user=user, final=True)
    next_semester = semester.academic_year.semesters.filter(start_date__gt=semester.end_date).order_by("start_date").first()
    if next_semester is not None:
        existing = SemesterStructureSnapshot.objects.filter(semester=next_semester).first()
        if existing is None or not existing.is_final:
            capture_semester_structure(
                semester=next_semester,
                user=user,
                final=False,
                source_snapshot=source,
                payload=source.payload,
            )
    return source
