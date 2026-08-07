"""Safe in-year section archiving and merge workflow."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from teachers.models import TeacherAssignment
from timetable.models import TimetableEntry

from .lifecycle import perform_lifecycle_action
from .models import Enrollment, Section


def section_merge_report(*, source, target):
    blockers = []
    if source.pk == target.pk:
        blockers.append("اختر شعبة هدف مختلفة عن الشعبة المصدر.")
    if source.academic_year_id != target.academic_year_id:
        blockers.append("الدمج يجب أن يكون داخل العام الدراسي نفسه.")
    if source.grade_id != target.grade_id:
        blockers.append("الدمج يجب أن يكون بين شعب الصف نفسه.")
    if source.branch_id != target.branch_id:
        blockers.append("الدمج بين فروع مختلفة غير مسموح.")
    if source.academic_year.is_closed:
        blockers.append("لا يمكن دمج شعب عام مغلق.")
    if not source.is_active or not target.is_active:
        blockers.append("يجب أن تكون الشعبة المصدر والهدف فعالتين.")

    enrollment_count = Enrollment.objects.filter(section=source, status="active").count()
    if target.capacity and target.active_enrollment_count + enrollment_count > target.capacity:
        blockers.append("سعة الشعبة الهدف لا تكفي للطلبة النشطين في الشعبة المصدر.")

    open_exams = source.exams.filter(
        status__in=["draft", "open", "submitted", "approved"],
        is_active=True,
    ).count()
    if open_exams:
        blockers.append(f"يوجد {open_exams} امتحانًا جاريًا في الشعبة المصدر؛ أكمل دورته قبل الدمج.")

    source_slots = set(
        source.timetable_entries.filter(is_active=True).values_list("day", "time_slot_id")
    )
    target_slots = set(
        target.timetable_entries.filter(is_active=True).values_list("day", "time_slot_id")
    )
    timetable_conflicts = len(source_slots.intersection(target_slots))
    if timetable_conflicts:
        blockers.append(f"يوجد {timetable_conflicts} تعارضًا زمنيًا مع جدول الشعبة الهدف.")

    return {
        "blockers": blockers,
        "metrics": {
            "students": enrollment_count,
            "assignments": TeacherAssignment.objects.filter(section=source, is_active=True).count(),
            "timetable_entries": len(source_slots),
            "open_exams": open_exams,
            "timetable_conflicts": timetable_conflicts,
        },
    }


@transaction.atomic
def merge_sections(*, source, target, reason, user=None, effective_date=None):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("سبب دمج الشعب إلزامي.")
    source = Section.objects.select_for_update().select_related(
        "academic_year", "grade", "branch", "homeroom_teacher"
    ).get(pk=source.pk)
    target = Section.objects.select_for_update().select_related(
        "academic_year", "grade", "branch", "homeroom_teacher"
    ).get(pk=target.pk)
    report = section_merge_report(source=source, target=target)
    if report["blockers"]:
        raise ValidationError(report["blockers"])

    assignments_copied = 0
    for assignment in TeacherAssignment.objects.select_for_update().filter(
        section=source,
        is_active=True,
    ).select_related("teacher", "subject"):
        target_assignment, created = TeacherAssignment.objects.get_or_create(
            teacher=assignment.teacher,
            academic_year=assignment.academic_year,
            section=target,
            subject=assignment.subject,
            defaults={
                "is_primary": assignment.is_primary,
                "is_active": True,
            },
        )
        if not created and not target_assignment.is_active:
            target_assignment.is_active = True
            target_assignment.is_primary = assignment.is_primary
            target_assignment.save()
        assignment.is_active = False
        assignment.save(update_fields=["is_active"])
        assignments_copied += 1

    timetable_copied = 0
    for entry in TimetableEntry.objects.select_for_update().filter(
        section=source,
        is_active=True,
    ).select_related("subject", "teacher", "time_slot"):
        entry.is_active = False
        TimetableEntry.objects.filter(pk=entry.pk).update(is_active=False)
        TimetableEntry.objects.create(
            academic_year=entry.academic_year,
            section=target,
            subject=entry.subject,
            teacher=entry.teacher,
            day=entry.day,
            time_slot=entry.time_slot,
            room=entry.room,
            is_active=True,
            generated_automatically=entry.generated_automatically,
        )
        timetable_copied += 1

    moved_students = 0
    enrollments = list(
        Enrollment.objects.select_for_update().filter(section=source, status="active").select_related("student")
    )
    for enrollment in enrollments:
        perform_lifecycle_action(
            student=enrollment.student,
            action="section_change",
            effective_date=effective_date or timezone.localdate(),
            target_year=source.academic_year,
            target_grade=source.grade,
            target_section=target,
            reason=reason,
            user=user,
        )
        moved_students += 1

    if target.homeroom_teacher_id is None and source.homeroom_teacher_id:
        target.homeroom_teacher = source.homeroom_teacher
        target.save(update_fields=["homeroom_teacher"])
    source.is_active = False
    source.is_default = False
    source.save(update_fields=["is_active", "is_default"])
    return source, target, {
        "students_moved": moved_students,
        "assignments_copied": assignments_copied,
        "timetable_entries_copied": timetable_copied,
    }
