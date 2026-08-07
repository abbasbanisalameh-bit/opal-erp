"""One operational workflow for the mandatory monthly evaluations."""

from django.db import transaction
from django.utils import timezone

from parent_portal.evaluation_services import teachers_for_family_students
from parent_portal.models import TeacherMonthlyEvaluation
from parent_portal.workflow import family_for_user, students_for_user
from teachers.permissions import is_teacher_user

from .models import MonthlyServiceEvaluation


class MonthlyEvaluationError(ValueError):
    """A safe, user-facing validation error for the monthly prompt."""


def _rating_from_payload(data, name, message):
    try:
        rating = int(data.get(name))
    except (TypeError, ValueError):
        raise MonthlyEvaluationError(message)
    if rating < 1 or rating > 5:
        raise MonthlyEvaluationError("قيمة التقييم غير صحيحة.")
    return rating


def _school_branch_for_user(user):
    teacher = getattr(user, "teacher_profile", None)
    if teacher is not None:
        return teacher.school, teacher.branch
    family = getattr(user, "family_account", None)
    if family is not None:
        return family.school, None
    profile = getattr(user, "profile", None)
    return getattr(profile, "school", None), getattr(profile, "branch", None)


def monthly_evaluation_prompt_for_user(user, today=None):
    """Return only the still-required rows for the current calendar month.

    Teachers evaluate the school's electronic services only. Guardians first
    evaluate their officially assigned teachers, then receive two separate
    general school evaluations: teaching quality and electronic services.
    """
    today = today or timezone.localdate()
    empty = None
    if not getattr(user, "is_authenticated", False) or user.is_superuser:
        return empty

    period = today.replace(day=1)
    school_evaluation = MonthlyServiceEvaluation.objects.filter(
        user=user, period=period
    ).first()

    if is_teacher_user(user):
        needs_service_evaluation = (
            school_evaluation is None
            or school_evaluation.electronic_services_submitted_at is None
        )
        return {
            "period": period,
            "teacher_rows": [],
            "stage": "teacher_services",
            "audience": "teacher",
        } if needs_service_evaluation else empty

    if user.is_staff:
        return empty

    family = family_for_user(user)
    students = students_for_user(user)
    if family is None:
        return empty
    rows = teachers_for_family_students(students)
    completed_ids = set(TeacherMonthlyEvaluation.objects.filter(
        family=family, period=period
    ).values_list("teacher_id", flat=True))
    pending_rows = [row for row in rows if row["teacher"].pk not in completed_ids]
    if pending_rows:
        return {
            "period": period,
            "teacher_rows": pending_rows,
            "stage": "parent_teacher",
            "audience": "parent",
        }

    # Records produced before this corrective update remain intact but have no
    # completion timestamps, so the guardian is prompted through the two new
    # independent general evaluations once.
    needs_teaching_quality_evaluation = (
        school_evaluation is None
        or school_evaluation.teaching_quality_submitted_at is None
    )
    if needs_teaching_quality_evaluation:
        return {
            "period": period,
            "teacher_rows": [],
            "stage": "parent_teaching_quality",
            "audience": "parent",
        }
    needs_electronic_services_evaluation = (
        school_evaluation is None
        or school_evaluation.electronic_services_submitted_at is None
    )
    if needs_electronic_services_evaluation:
        return {
            "period": period,
            "teacher_rows": [],
            "stage": "parent_electronic_services",
            "audience": "parent",
        }
    return empty


def submit_monthly_evaluations(user, data, today=None):
    """Persist all unfinished rows in a single atomic monthly submission."""
    today = today or timezone.localdate()
    prompt = monthly_evaluation_prompt_for_user(user, today=today)
    if prompt is None:
        return False

    teacher_ratings = {}
    for row in prompt["teacher_rows"]:
        teacher_id = row["teacher"].pk
        teacher_ratings[teacher_id] = _rating_from_payload(
            data,
            f"rating_{teacher_id}",
            "يجب تقييم جميع المعلمين من نجمة إلى خمس نجوم.",
        )
    teaching_rating = None
    service_rating = None
    if prompt["stage"] in {"teacher_services", "parent_electronic_services"}:
        service_rating = _rating_from_payload(
            data,
            "service_rating",
            "يجب تقييم الخدمات الإلكترونية من نجمة إلى خمس نجوم.",
        )
    elif prompt["stage"] == "parent_teaching_quality":
        teaching_rating = _rating_from_payload(
            data,
            "teaching_rating",
            "يجب تقييم جودة التدريس من نجمة إلى خمس نجوم.",
        )

    school, branch = _school_branch_for_user(user)
    with transaction.atomic():
        if prompt["audience"] == "parent":
            family = family_for_user(user)
            for teacher_id, rating in teacher_ratings.items():
                TeacherMonthlyEvaluation.objects.update_or_create(
                    family=family,
                    teacher_id=teacher_id,
                    period=prompt["period"],
                    defaults={
                        "teaching_quality_rating": rating,
                        # The former service field is kept nullable for historic
                        # records only.  The central service model is the source
                        # of truth for all new electronic-services ratings.
                        "electronic_services_rating": None,
                    },
                )
        if teaching_rating is not None:
            MonthlyServiceEvaluation.objects.update_or_create(
                user=user,
                period=prompt["period"],
                defaults={
                    "school": school,
                    "branch": branch,
                    "teaching_quality_rating": teaching_rating,
                    "teaching_quality_submitted_at": timezone.now(),
                },
            )
        if service_rating is not None:
            MonthlyServiceEvaluation.objects.update_or_create(
                user=user,
                period=prompt["period"],
                defaults={
                    "school": school,
                    "branch": branch,
                    "electronic_services_rating": service_rating,
                    "electronic_services_submitted_at": timezone.now(),
                },
            )
    return True
