"""Atomic, idempotent preparation and annual student transition services."""

from collections import Counter

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import AcademicYear

from .lifecycle import perform_lifecycle_action
from .models import Enrollment, Grade, Section, Subject


def _validate_year_pair(source_year, target_year):
    if source_year.pk == target_year.pk:
        raise ValidationError("يجب أن يكون العام الجديد مختلفًا عن العام المصدر.")
    if source_year.school_id != target_year.school_id:
        raise ValidationError("العامان يجب أن يتبعا المدرسة نفسها.")
    if target_year.is_closed:
        raise ValidationError("العام المستهدف مغلق ولا يقبل التهيئة أو الانتقال.")
    if target_year.start_date <= source_year.start_date:
        raise ValidationError("العام المستهدف يجب أن يأتي بعد العام المصدر زمنيًا.")


def next_year_preparation_report(*, source_year, target_year):
    """Read-only preview of the idempotent structure preparation."""
    from admissions.models import GradeFee
    from teachers.models import TeacherAssignment
    from timetable.models import TimetableEntry

    _validate_year_pair(source_year, target_year)
    payload = {}
    if source_year.is_closed:
        second = source_year.semesters.filter(code="second").first()
        if second is not None:
            try:
                payload = second.structure_snapshot.payload or {}
            except Exception:
                payload = {}

    def has_field(model, name):
        try:
            model._meta.get_field(name)
            return True
        except Exception:
            return False

    def count(model, key):
        if source_year.is_closed and key in payload:
            return sum(1 for row in payload[key] if row.get("is_active"))
        queryset = model.objects.filter(academic_year=source_year)
        if not source_year.is_closed and has_field(model, "is_active"):
            queryset = queryset.filter(is_active=True)
        return queryset.count()

    return {
        "already_prepared": bool(
            target_year.prepared_at and target_year.preparation_source_id == source_year.pk
        ),
        "sections": count(Section, "sections"),
        "fees": count(GradeFee, "grade_fees"),
        "subject_plans": count(Subject, "subjects"),
        "assignments": count(TeacherAssignment, "assignments"),
        "timetable_entries": count(TimetableEntry, "timetable"),
        "students": 0,
        "invoices": 0,
        "marks": 0,
        "attendance": 0,
    }


@transaction.atomic
def prepare_next_year(*, source_year, target_year, user=None):
    """Copy next-year structure; never copy students, marks, invoices or attendance."""
    from admissions.models import GradeFee
    from teachers.models import TeacherAssignment
    from timetable.models import TimetableEntry

    source_year = AcademicYear.objects.select_for_update().get(pk=source_year.pk)
    target_year = AcademicYear.objects.select_for_update().get(pk=target_year.pk)
    _validate_year_pair(source_year, target_year)
    if target_year.preparation_source_id and target_year.preparation_source_id != source_year.pk:
        raise ValidationError("هذا العام مهيأ مسبقًا من عام مصدر مختلف.")
    if target_year.prepared_at and target_year.preparation_source_id == source_year.pk:
        return target_year, {
            "already_prepared": True,
            "sections_created": 0,
            "sections_updated": 0,
            "fees_copied": 0,
            "subject_plans_copied": 0,
            "assignments_copied": 0,
            "timetable_entries_copied": 0,
        }

    snapshot_payload = {}
    if source_year.is_closed:
        second = source_year.semesters.filter(code="second").first()
        if second is not None:
            try:
                snapshot_payload = second.structure_snapshot.payload or {}
            except Exception:
                snapshot_payload = {}

    def has_field(model, name):
        try:
            model._meta.get_field(name)
            return True
        except Exception:
            return False

    def source_queryset(model, payload_key):
        queryset = model.objects.filter(academic_year=source_year)
        if source_year.is_closed and payload_key in snapshot_payload:
            active_ids = [row["id"] for row in snapshot_payload[payload_key] if row.get("is_active")]
            return queryset.filter(pk__in=active_ids)
        if not source_year.is_closed and has_field(model, "is_active"):
            return queryset.filter(is_active=True)
        return queryset

    sections_created = sections_updated = fees_copied = subject_plans_copied = 0
    assignments_copied = timetable_entries_copied = 0
    section_map = {}
    source_sections = source_queryset(Section, "sections").select_related("grade", "branch", "homeroom_teacher")
    for source in source_sections:
        target_is_active = True if source_year.is_closed else source.is_active
        target, created = Section.objects.get_or_create(
            academic_year=target_year,
            branch=source.branch,
            grade=source.grade,
            name=source.name,
            defaults={
                "capacity": source.capacity,
                "homeroom_teacher": source.homeroom_teacher if getattr(source.homeroom_teacher, "is_active", False) else None,
                "is_default": source.is_default,
                "is_active": target_is_active,
            },
        )
        if created:
            sections_created += 1
        else:
            target.capacity = source.capacity
            target.is_default = source.is_default
            target.is_active = target_is_active
            if getattr(source.homeroom_teacher, "is_active", False):
                target.homeroom_teacher = source.homeroom_teacher
            target.save()
            sections_updated += 1
        section_map[source.pk] = target

    for source in source_queryset(GradeFee, "grade_fees").select_related("grade"):
        target = GradeFee.objects.filter(
            school=source.school,
            academic_year=target_year,
            grade=source.grade,
        ).order_by("pk").first()
        if target is None:
            target = GradeFee(school=source.school, academic_year=target_year, grade=source.grade)
        target.tuition_fee = source.tuition_fee
        target.is_active = True if source_year.is_closed else source.is_active
        target.save()
        fees_copied += 1

    subject_map = {}
    for source in source_queryset(Subject, "subjects").select_related("grade"):
        target = Subject.objects.filter(
            academic_year=target_year,
            grade=source.grade,
            canonical_key=source.canonical_key,
        ).first()
        if target is None:
            target = Subject.objects.filter(
                academic_year=target_year,
                grade=source.grade,
                name=source.name,
            ).first()
        if target is None:
            target = Subject(academic_year=target_year, grade=source.grade)
        target.name = source.name
        target.code = source.code
        target.weekly_periods = source.weekly_periods
        target.is_required = source.is_required
        target.color = source.color
        target.is_active = True if source_year.is_closed else source.is_active
        target.save()
        subject_map[source.pk] = target
        subject_plans_copied += 1

    assignments = source_queryset(TeacherAssignment, "assignments").select_related(
        "teacher", "section", "subject"
    )
    for source in assignments:
        target_section = section_map.get(source.section_id)
        target_subject = subject_map.get(source.subject_id)
        # ``source_queryset`` already applies the frozen semester snapshot
        # when the source year is closed.  The live source rows are normally
        # deactivated after closure, so checking ``source.subject.is_active``
        # here would incorrectly discard an assignment that the snapshot
        # explicitly marked active.
        if target_section is None or target_subject is None or not source.teacher.is_active:
            continue
        TeacherAssignment.objects.update_or_create(
            teacher=source.teacher,
            academic_year=target_year,
            section=target_section,
            subject=target_subject,
            defaults={
                "is_primary": source.is_primary,
                "is_active": True,
            },
        )
        assignments_copied += 1

    timetable_entries = source_queryset(TimetableEntry, "timetable").select_related(
        "section", "subject", "teacher", "time_slot"
    )
    for source in timetable_entries:
        target_section = section_map.get(source.section_id)
        target_subject = subject_map.get(source.subject_id)
        if target_section is None or target_subject is None or (source.teacher_id and not source.teacher.is_active):
            continue
        TimetableEntry.objects.update_or_create(
            academic_year=target_year,
            section=target_section,
            day=source.day,
            time_slot=source.time_slot,
            defaults={
                "subject": target_subject,
                "teacher": source.teacher,
                "room": source.room,
                "is_active": True,
                "generated_automatically": source.generated_automatically,
            },
        )
        timetable_entries_copied += 1

    target_year.preparation_source = source_year
    target_year.prepared_at = target_year.prepared_at or timezone.now()
    target_year.prepared_by = user if getattr(user, "is_authenticated", False) else None
    target_year.save(update_fields=["preparation_source", "prepared_at", "prepared_by"])
    return target_year, {
        "already_prepared": False,
        "sections_created": sections_created,
        "sections_updated": sections_updated,
        "fees_copied": fees_copied,
        "subject_plans_copied": subject_plans_copied,
        "assignments_copied": assignments_copied,
        "timetable_entries_copied": timetable_entries_copied,
    }


def annual_transition_report(*, source_year, target_year):
    _validate_year_pair(source_year, target_year)
    blockers = []
    if not source_year.is_closed:
        blockers.append("يجب إغلاق العام المصدر أكاديميًا قبل الانتقال.")
    if not target_year.prepared_at:
        blockers.append("يجب تهيئة العام الجديد قبل الانتقال.")
    if target_year.preparation_source_id not in {None, source_year.pk}:
        blockers.append("العام الجديد مهيأ من عام مصدر مختلف.")

    grades = list(Grade.objects.filter(school=source_year.school, is_active=True).order_by("order", "pk"))
    next_grade = {grades[index].pk: grades[index + 1] for index in range(len(grades) - 1)}
    enrollments = list(
        Enrollment.objects.filter(academic_year=source_year, status="active")
        .select_related("student", "grade", "section")
        .order_by("student__full_name")
    )
    target_sections = list(
        Section.objects.filter(academic_year=target_year, is_active=True)
        .select_related("grade")
        .order_by("grade__order", "is_default", "name")
    )
    sections_by_grade = {}
    for section in target_sections:
        sections_by_grade.setdefault(section.grade_id, []).append(section)

    planned_capacity = Counter()
    plan = []
    for enrollment in enrollments:
        grade = next_grade.get(enrollment.grade_id)
        if grade is None:
            plan.append({"enrollment": enrollment, "action": "graduate", "target_grade": None, "target_section": None})
            continue
        candidates = sections_by_grade.get(grade.pk, [])
        same_name = next((item for item in candidates if enrollment.section_id and item.name == enrollment.section.name), None)
        target_section = same_name or next((item for item in candidates if item.is_default), None) or (candidates[0] if candidates else None)
        if target_section is None:
            blockers.append(f"لا توجد شعبة فعالة للصف {grade.name} في العام الجديد.")
            continue
        planned_capacity[target_section.pk] += 1
        plan.append({"enrollment": enrollment, "action": "promote", "target_grade": grade, "target_section": target_section})

    capacity_warnings = []
    sections_by_id = {section.pk: section for section in target_sections}
    for section_id, incoming_count in planned_capacity.items():
        section = sections_by_id[section_id]
        projected_count = section.active_enrollment_count + incoming_count
        if section.capacity and projected_count > section.capacity:
            capacity_warnings.append({
                "section": section,
                "projected_count": projected_count,
                "capacity": section.capacity,
                "excess": projected_count - section.capacity,
                "message": (
                    f"سيصبح عدد طلبة {section} بعد الانتقال {projected_count} طالبًا، "
                    f"بينما سعته المعتمدة {section.capacity}. "
                    "الانتقال مسموح، ويجب على الإدارة مراجعة تقسيم الصف إلى شعب عند الحاجة."
                ),
            })

    return {
        "blockers": list(dict.fromkeys(blockers)),
        "plan": plan,
        "warnings": capacity_warnings,
        "metrics": {
            "students": len(enrollments),
            "promotions": sum(1 for item in plan if item["action"] == "promote"),
            "graduations": sum(1 for item in plan if item["action"] == "graduate"),
        },
    }


@transaction.atomic
def execute_annual_transition(*, source_year, target_year, user=None, effective_date=None):
    source_year = AcademicYear.objects.select_for_update().get(pk=source_year.pk)
    target_year = AcademicYear.objects.select_for_update().get(pk=target_year.pk)
    if source_year.transition_completed_at:
        return source_year, {"already_completed": True, "promotions": 0, "graduations": 0}
    report = annual_transition_report(source_year=source_year, target_year=target_year)
    if report["blockers"]:
        raise ValidationError(report["blockers"])

    effective_date = effective_date or target_year.start_date
    for item in report["plan"]:
        perform_lifecycle_action(
            student=item["enrollment"].student,
            action=item["action"],
            effective_date=effective_date,
            target_year=target_year if item["action"] == "promote" else None,
            target_grade=item["target_grade"],
            target_section=item["target_section"],
            reason=f"انتقال سنوي آلي من {source_year.name} إلى {target_year.name}",
            user=user,
            allow_capacity_overflow=item["action"] == "promote",
        )

    source_year.transition_completed_at = timezone.now()
    source_year.transition_completed_by = user if getattr(user, "is_authenticated", False) else None
    source_year.save(update_fields=["transition_completed_at", "transition_completed_by"])
    return source_year, {
        "already_completed": False,
        **report["metrics"],
        "capacity_warnings": [warning["message"] for warning in report.get("warnings", [])],
    }
