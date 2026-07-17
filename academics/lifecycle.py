from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Enrollment, StudentLifecycleEvent


def _validate_target(target_year, target_grade, target_section):
    if not target_year or not target_grade:
        raise ValidationError("يجب تحديد العام والصف المستهدفين.")
    if target_year.is_closed:
        raise ValidationError("العام الدراسي المستهدف مغلق ولا يقبل قيودًا جديدة.")
    if target_section:
        if target_section.grade_id != target_grade.id:
            raise ValidationError("الشعبة المستهدفة لا تتبع الصف المحدد.")
        if target_section.academic_year_id and target_section.academic_year_id != target_year.id:
            raise ValidationError("الشعبة المستهدفة لا تتبع العام الدراسي المحدد.")
        if target_section.capacity and target_section.active_enrollment_count >= target_section.capacity:
            raise ValidationError("الشعبة المستهدفة ممتلئة ولا يوجد فيها مقعد شاغر.")


@transaction.atomic
def perform_lifecycle_action(
    *,
    student,
    action,
    effective_date=None,
    target_year=None,
    target_grade=None,
    target_section=None,
    reason="",
    user=None,
):
    effective_date = effective_date or timezone.localdate()
    current = (
        student.enrollments.filter(status="active")
        .select_related("academic_year", "grade", "section")
        .order_by("-academic_year__start_date")
        .first()
    )
    to_enrollment = None

    if current and current.academic_year.is_closed:
        raise ValidationError("قيد الطالب يتبع عامًا مغلقًا ولا يمكن تعديله.")

    if action in {"promote", "reenroll", "section_change"}:
        _validate_target(target_year, target_grade, target_section)

    if action == "section_change":
        if not current:
            raise ValidationError("لا يوجد قيد نشط للطالب.")
        if current.academic_year_id != target_year.id:
            raise ValidationError("تغيير الشعبة يجب أن يكون داخل العام الدراسي نفسه.")
        current.grade = target_grade
        current.section = target_section
        current.status_reason = reason
        current.save(update_fields=["grade", "section", "status_reason"])
        to_enrollment = current

    elif action in {"promote", "reenroll"}:
        if current and current.academic_year_id != target_year.id:
            current.status = "completed"
            current.ended_at = effective_date
            current.status_reason = reason or "إغلاق القيد عند الانتقال إلى عام دراسي جديد"
            current.save(update_fields=["status", "ended_at", "status_reason"])
        to_enrollment, _ = Enrollment.objects.update_or_create(
            student=student,
            academic_year=target_year,
            defaults={
                "grade": target_grade,
                "section": target_section,
                "status": "active",
                "joined_at": effective_date,
                "ended_at": None,
                "status_reason": reason,
            },
        )
        student.status = "active"
        student.is_active = True

    elif action == "transfer":
        if not current:
            raise ValidationError("لا يوجد قيد نشط للطالب.")
        current.status = "transferred"
        current.ended_at = effective_date
        current.status_reason = reason
        current.save(update_fields=["status", "ended_at", "status_reason"])
        student.status = "transferred"
        student.is_active = False

    elif action == "withdraw":
        if not current:
            raise ValidationError("لا يوجد قيد نشط للطالب.")
        current.status = "withdrawn"
        current.ended_at = effective_date
        current.status_reason = reason
        current.save(update_fields=["status", "ended_at", "status_reason"])
        student.status = "archived"
        student.is_active = False

    elif action == "graduate":
        if not current:
            raise ValidationError("لا يوجد قيد نشط للطالب.")
        current.status = "graduated"
        current.ended_at = effective_date
        current.status_reason = reason
        current.save(update_fields=["status", "ended_at", "status_reason"])
        student.status = "graduated"
        student.is_active = False

    else:
        raise ValidationError("الإجراء المطلوب غير معروف.")

    if to_enrollment:
        student.grade = to_enrollment.grade.name if to_enrollment.grade else ""
        student.section = to_enrollment.section.name if to_enrollment.section else ""
    student.save(update_fields=["status", "is_active", "grade", "section", "updated_at"])

    event = StudentLifecycleEvent.objects.create(
        student=student,
        action=action,
        from_enrollment=current,
        to_enrollment=to_enrollment,
        effective_date=effective_date,
        reason=reason,
        performed_by=user,
    )
    return event
