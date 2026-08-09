from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from academics.models import Enrollment
from teachers.models import TeacherAssignment

from .models import (
    LearningAccessSettings,
    LearningAccount,
    LearningCourse,
    LearningGradeAccessOverride,
    LearningStudentAccessOverride,
    LearningStudentProfile,
    LearningSubject,
    LearningTeacherProfile,
)


def current_student_enrollment(student):
    return (
        Enrollment.objects.filter(student=student, status="active")
        .select_related("academic_year", "grade", "section", "academic_year__school")
        .order_by("-academic_year__is_current", "-academic_year__start_date", "-pk")
        .first()
    )


def access_settings_for_school(school):
    settings, _created = LearningAccessSettings.objects.get_or_create(school=school)
    return settings


def student_learning_access(student):
    """Resolve student access using student > grade > school precedence."""
    enrollment = current_student_enrollment(student)
    if enrollment is None:
        return {
            "enabled": False,
            "source": "none",
            "label": "لا يوجد قيد أكاديمي فعال",
            "enrollment": None,
            "settings": None,
        }
    settings = access_settings_for_school(enrollment.academic_year.school)
    student_override = LearningStudentAccessOverride.objects.filter(
        settings=settings, student=student
    ).first()
    if student_override is not None:
        return {
            "enabled": student_override.is_enabled,
            "source": "student",
            "label": "استثناء خاص بالطالب",
            "enrollment": enrollment,
            "settings": settings,
        }
    grade_override = LearningGradeAccessOverride.objects.filter(
        settings=settings, grade=enrollment.grade
    ).first()
    if grade_override is not None:
        return {
            "enabled": grade_override.is_enabled,
            "source": "grade",
            "label": f"إعداد {enrollment.grade.name}",
            "enrollment": enrollment,
            "settings": settings,
        }
    return {
        "enabled": settings.parent_default_enabled,
        "source": "global",
        "label": "الإعداد العام",
        "enrollment": enrollment,
        "settings": settings,
    }


def teacher_learning_access(teacher):
    if teacher is None or not teacher.is_active or not teacher.school_id:
        return False
    return access_settings_for_school(teacher.school).teacher_sso_enabled


def _managed_email(prefix, pk):
    return f"{prefix}-{pk}@school.opal.local"


@transaction.atomic
def ensure_student_learning_account(student):
    profile = LearningStudentProfile.objects.select_related("account").filter(student=student).first()
    if profile is not None:
        account = profile.account
        updates = []
        now = timezone.now()
        if account.full_name != student.full_name:
            account.full_name = student.full_name
            updates.append("full_name")
        if not account.is_active:
            account.is_active = True
            updates.append("is_active")
        if not account.is_school_managed:
            account.is_school_managed = True
            updates.append("is_school_managed")
        # School-managed identities use the ERP credential source.  Their
        # synthetic @school.opal.local address is never an end-user mailbox,
        # so keep legal/email gates satisfied for API token issuance.
        if account.terms_accepted_at is None:
            account.terms_accepted_at = now
            updates.append("terms_accepted_at")
        if account.privacy_accepted_at is None:
            account.privacy_accepted_at = now
            updates.append("privacy_accepted_at")
        if account.email_verified_at is None:
            account.email_verified_at = now
            updates.append("email_verified_at")
        if updates:
            updates.append("updated_at")
            account.save(update_fields=updates)
        return account

    now = timezone.now()
    account = LearningAccount(
        email=_managed_email("student", student.pk),
        full_name=student.full_name,
        phone=student.phone or "",
        role=LearningAccount.Role.LEARNER,
        is_active=True,
        is_school_managed=True,
        terms_accepted_at=now,
        privacy_accepted_at=now,
        email_verified_at=now,
    )
    account.set_password(None)
    account.save()
    LearningStudentProfile.objects.create(student=student, account=account)
    return account


@transaction.atomic
def ensure_teacher_learning_account(teacher):
    profile = LearningTeacherProfile.objects.select_related("account").filter(teacher=teacher).first()
    if profile is not None:
        account = profile.account
        updates = []
        now = timezone.now()
        if account.full_name != teacher.full_name:
            account.full_name = teacher.full_name
            updates.append("full_name")
        if not account.is_active:
            account.is_active = True
            updates.append("is_active")
        if not account.is_school_managed:
            account.is_school_managed = True
            updates.append("is_school_managed")
        if account.terms_accepted_at is None:
            account.terms_accepted_at = now
            updates.append("terms_accepted_at")
        if account.privacy_accepted_at is None:
            account.privacy_accepted_at = now
            updates.append("privacy_accepted_at")
        if account.email_verified_at is None:
            account.email_verified_at = now
            updates.append("email_verified_at")
        if updates:
            updates.append("updated_at")
            account.save(update_fields=updates)
        return account

    now = timezone.now()
    account = LearningAccount(
        email=_managed_email("teacher", teacher.pk),
        full_name=teacher.full_name,
        phone=teacher.phone or "",
        role=LearningAccount.Role.TEACHER,
        is_active=True,
        is_school_managed=True,
        terms_accepted_at=now,
        privacy_accepted_at=now,
        email_verified_at=now,
    )
    account.set_password(None)
    account.save()
    LearningTeacherProfile.objects.create(teacher=teacher, account=account)
    return account


def managed_student_for_account(account):
    if not account or not account.is_school_managed or account.role != LearningAccount.Role.LEARNER:
        return None
    profile = LearningStudentProfile.objects.select_related("student").filter(account=account).first()
    return profile.student if profile else None


def managed_teacher_for_account(account):
    if not account or not account.is_school_managed or account.role != LearningAccount.Role.TEACHER:
        return None
    profile = LearningTeacherProfile.objects.select_related("teacher", "teacher__school").filter(account=account).first()
    return profile.teacher if profile else None


def eligible_courses_for_student(student):
    access = student_learning_access(student)
    enrollment = access["enrollment"]
    base = LearningCourse.objects.filter(
        status=LearningCourse.Status.PUBLISHED,
        subject__is_active=True,
    )
    if not access["enabled"] or enrollment is None:
        return base.none()
    # School-managed courses are restricted to the current student's academic
    # year/grade, and optionally to the exact section. Unlinked public courses
    # are intentionally excluded from the school gateway.
    return base.filter(
        academic_subject__academic_year=enrollment.academic_year,
        academic_subject__grade=enrollment.grade,
    ).filter(
        Q(academic_section__isnull=True) | Q(academic_section=enrollment.section)
    )


def school_managed_account_can_see_course(account, course):
    student = managed_student_for_account(account)
    if student is None:
        return True
    return eligible_courses_for_student(student).filter(pk=course.pk).exists()


def official_teacher_assignments(teacher):
    return TeacherAssignment.objects.filter(
        teacher=teacher,
        is_active=True,
        academic_year__is_current=True,
        section__is_active=True,
        subject__is_active=True,
    ).select_related("academic_year", "section", "section__grade", "subject")


def assignment_for_teacher_or_error(teacher, assignment_id):
    assignment = official_teacher_assignments(teacher).filter(pk=assignment_id).first()
    if assignment is None:
        raise ValidationError("التكليف المحدد ليس ضمن المواد والشعب المسندة لك رسميًا.")
    return assignment


def ensure_learning_subject_for_academic_subject(subject):
    from django.utils.text import slugify

    base_slug = slugify(subject.name, allow_unicode=True) or f"subject-{subject.pk}"
    item = LearningSubject.objects.filter(name=subject.name).first()
    if item is not None:
        if not item.is_active:
            item.is_active = True
            item.save(update_fields=["is_active"])
        return item
    slug = base_slug
    suffix = 2
    while LearningSubject.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return LearningSubject.objects.create(name=subject.name, slug=slug, is_active=True)


def assert_parent_can_open_student(user, student):
    from parent_portal.models import FamilyStudent

    allowed = FamilyStudent.objects.filter(
        family__user=user,
        family__is_active=True,
        student=student,
        is_active=True,
    ).exists()
    if not allowed:
        raise PermissionDenied("لا تملك صلاحية الدخول إلى منصة هذا الطالب.")
    access = student_learning_access(student)
    if not access["enabled"]:
        raise PermissionDenied("منصة أوبال التعليمية غير متاحة لهذا الطالب حاليًا.")
    return access
