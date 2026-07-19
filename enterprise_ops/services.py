from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from core.models import AuditLog

from .models import ApprovalAction, FeedbackTicket, Notification


def feedback_satisfaction_snapshot(queryset=None, today=None):
    """Return one-query satisfaction analytics for management dashboards.

    Ratings are stored on every feedback ticket from 1 to 5. The returned
    percentages are safe for empty datasets and ready for charts/templates.
    """
    qs = queryset if queryset is not None else FeedbackTicket.objects.all()
    today = today or timezone.localdate()
    recent_start = today - timedelta(days=29)
    previous_start = recent_start - timedelta(days=30)

    metrics = {
        "total": Count("id"),
        "teaching_average": Avg("teaching_quality_rating"),
        "electronic_average": Avg("electronic_services_rating"),
        "teaching_positive": Count("id", filter=Q(teaching_quality_rating__gte=4)),
        "electronic_positive": Count("id", filter=Q(electronic_services_rating__gte=4)),
        "both_positive": Count(
            "id",
            filter=Q(teaching_quality_rating__gte=4, electronic_services_rating__gte=4),
        ),
        "recent_total": Count("id", filter=Q(created_at__date__gte=recent_start)),
        "recent_teaching_average": Avg(
            "teaching_quality_rating",
            filter=Q(created_at__date__gte=recent_start),
        ),
        "recent_electronic_average": Avg(
            "electronic_services_rating",
            filter=Q(created_at__date__gte=recent_start),
        ),
        "previous_teaching_average": Avg(
            "teaching_quality_rating",
            filter=Q(created_at__date__gte=previous_start, created_at__date__lt=recent_start),
        ),
        "previous_electronic_average": Avg(
            "electronic_services_rating",
            filter=Q(created_at__date__gte=previous_start, created_at__date__lt=recent_start),
        ),
        "teacher_responses": Count("id", filter=Q(sender__teacher_profile__isnull=False)),
        "parent_responses": Count("id", filter=Q(sender__family_account__isnull=False)),
    }
    for score in range(1, 6):
        metrics[f"teaching_{score}"] = Count(
            "id", filter=Q(teaching_quality_rating=score)
        )
        metrics[f"electronic_{score}"] = Count(
            "id", filter=Q(electronic_services_rating=score)
        )

    raw = qs.aggregate(**metrics)
    total = raw["total"] or 0

    def score(value):
        return round(float(value or 0), 2)

    def percent_from_average(value):
        return round((score(value) / 5) * 100, 1) if total else 0

    def positive_percent(value):
        return round(((value or 0) / total) * 100, 1) if total else 0

    teaching_average = score(raw["teaching_average"])
    electronic_average = score(raw["electronic_average"])
    overall_average = round((teaching_average + electronic_average) / 2, 2) if total else 0
    overall_percent = round((overall_average / 5) * 100, 1) if total else 0

    recent_teaching = score(raw["recent_teaching_average"])
    recent_electronic = score(raw["recent_electronic_average"])
    previous_teaching = score(raw["previous_teaching_average"])
    previous_electronic = score(raw["previous_electronic_average"])
    recent_overall = round((recent_teaching + recent_electronic) / 2, 2) if raw["recent_total"] else 0
    previous_overall = (
        round((previous_teaching + previous_electronic) / 2, 2)
        if raw["previous_teaching_average"] is not None or raw["previous_electronic_average"] is not None
        else 0
    )
    trend_delta = round(recent_overall - previous_overall, 2) if recent_overall and previous_overall else 0

    if not total:
        satisfaction_label = "لا توجد تقييمات بعد"
        satisfaction_level = "empty"
    elif overall_percent >= 85:
        satisfaction_label = "رضا ممتاز"
        satisfaction_level = "excellent"
    elif overall_percent >= 70:
        satisfaction_label = "رضا جيد"
        satisfaction_level = "good"
    elif overall_percent >= 50:
        satisfaction_label = "رضا متوسط"
        satisfaction_level = "medium"
    else:
        satisfaction_label = "يحتاج إلى تحسين"
        satisfaction_level = "low"

    return {
        "feedback_total": total,
        "feedback_recent_total": raw["recent_total"] or 0,
        "teaching_rating_average": teaching_average,
        "electronic_rating_average": electronic_average,
        "overall_rating_average": overall_average,
        "teaching_satisfaction_percent": percent_from_average(raw["teaching_average"]),
        "electronic_satisfaction_percent": percent_from_average(raw["electronic_average"]),
        "overall_satisfaction_percent": overall_percent,
        "teaching_positive_percent": positive_percent(raw["teaching_positive"]),
        "electronic_positive_percent": positive_percent(raw["electronic_positive"]),
        "both_positive_percent": positive_percent(raw["both_positive"]),
        "teaching_rating_distribution": [raw[f"teaching_{score}"] or 0 for score in range(1, 6)],
        "electronic_rating_distribution": [raw[f"electronic_{score}"] or 0 for score in range(1, 6)],
        "feedback_teacher_responses": raw["teacher_responses"] or 0,
        "feedback_parent_responses": raw["parent_responses"] or 0,
        "feedback_recent_overall_average": recent_overall,
        "feedback_trend_delta": trend_delta,
        "feedback_trend_abs": abs(trend_delta),
        "feedback_satisfaction_label": satisfaction_label,
        "feedback_satisfaction_level": satisfaction_level,
        "feedback_period_start": recent_start,
    }


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


def _user_scope(user):
    try:
        return user.profile.school, user.profile.branch
    except Exception:
        teacher = getattr(user, "teacher_profile", None)
        if teacher is not None:
            return teacher.school, teacher.branch
        family = getattr(user, "family_account", None)
        if family is not None:
            return family.school, None
        return None, None


def audit(request, action, model_name="", object_id="", description=""):
    """Record an audit event without breaking the user's primary operation.

    A stale production audit schema must never turn mark entry, feedback, or
    another successful school operation into an HTTP 500 response.
    """
    school, branch = _user_scope(request.user) if getattr(request, "user", None) and request.user.is_authenticated else (None, None)
    try:
        return AuditLog.objects.create(
            user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
            school=school,
            branch=branch,
            action=action,
            model_name=model_name,
            object_id=str(object_id or ""),
            description=description,
            ip_address=client_ip(request),
        )
    except DatabaseError:
        return None


def notify(recipient, title, message="", level="info", link="", event_key="", sound_enabled=True):
    if not recipient:
        return None
    values = {
        "title": title,
        "message": message,
        "level": level,
        "link": link,
        "sound_enabled": sound_enabled,
    }
    if event_key:
        item, _ = Notification.objects.get_or_create(
            recipient=recipient,
            event_key=event_key,
            defaults=values,
        )
        return item
    return Notification.objects.create(recipient=recipient, **values)


def management_recipients():
    from django.db.models import Q

    return User.objects.filter(is_active=True).filter(
        Q(is_staff=True)
        | Q(is_superuser=True)
        | Q(profile__role__code__in={"super_admin", "school_owner", "principal", "accountant", "secretary"})
    ).distinct()


def notify_management(title, message="", level="info", link="", exclude_user=None):
    qs = management_recipients()
    if exclude_user:
        qs = qs.exclude(pk=exclude_user.pk)
    return [notify(user, title, message, level, link) for user in qs]


def broadcast_recipients(message):
    """Return distinct active users targeted by a circular or direct alert."""
    if message.message_type == "teacher_alert":
        user = getattr(message.specific_teacher, "user", None)
        return User.objects.filter(pk=getattr(user, "pk", None), is_active=True)

    teacher_ids = User.objects.filter(
        is_active=True,
        teacher_profile__is_active=True,
    ).values_list("pk", flat=True)
    parent_ids = User.objects.filter(
        is_active=True,
        family_account__is_active=True,
        family_account__merged_into__isnull=True,
    ).values_list("pk", flat=True)

    if message.audience == "teachers":
        return User.objects.filter(pk__in=teacher_ids).distinct()
    if message.audience == "parents":
        return User.objects.filter(pk__in=parent_ids).distinct()

    # "الجميع" includes management, teachers, and parents with active accounts.
    return User.objects.filter(is_active=True).filter(
        models_q_for_all_system_users()
    ).distinct()


def models_q_for_all_system_users():
    # Local import avoids exposing django.db.models at module import in callers.
    from django.db.models import Q

    return (
        Q(is_staff=True)
        | Q(is_superuser=True)
        | Q(profile__role__code__in={"super_admin", "school_owner", "principal", "accountant", "secretary"})
        | Q(teacher_profile__is_active=True)
        | Q(family_account__is_active=True, family_account__merged_into__isnull=True)
    )


def send_broadcast_notifications(message):
    recipients = list(broadcast_recipients(message))
    level = "warning" if message.message_type == "teacher_alert" else "info"
    link = "/enterprise/notifications/"
    with transaction.atomic():
        for recipient in recipients:
            notify(
                recipient,
                message.title,
                message.message,
                level=level,
                link=link,
                event_key=f"broadcast:{message.pk}:user:{recipient.pk}",
                sound_enabled=True,
            )
        message.recipients_count = len(recipients)
        message.save(update_fields=["recipients_count"])
    return len(recipients)


def add_workflow_action(workflow, actor, action, note="", from_status="", to_status=""):
    return ApprovalAction.objects.create(
        workflow=workflow,
        actor=actor,
        action=action,
        note=note,
        from_status=from_status,
        to_status=to_status,
    )


ALLOWED_TRANSITIONS = {
    "new": {"review", "approve", "reject", "return", "comment"},
    "review": {"approve", "reject", "return", "comment"},
    "returned": {"review", "reject", "comment"},
    "approved": {"archive", "comment"},
    "rejected": {"archive", "comment"},
    "archived": {"comment"},
}


def _apply_related_decision(workflow, action, actor, note):
    if workflow.related_app == "accounting" and workflow.related_model == "DiscountRequest" and action in {"approve", "reject"}:
        from accounting.models import DiscountRequest
        from accounting.services import decide_discount

        item = DiscountRequest.objects.filter(pk=workflow.related_object_id).first()
        if item and item.status == "pending":
            decide_discount(item, actor, action == "approve", note)


def transition_workflow(workflow, actor, action, note=""):
    allowed = ALLOWED_TRANSITIONS.get(workflow.status, {"comment"})
    if action not in allowed:
        raise ValidationError(f"لا يمكن تنفيذ الإجراء {action} عندما تكون الحالة {workflow.get_status_display()}.")
    mapping = {
        "review": "review",
        "approve": "approved",
        "reject": "rejected",
        "return": "returned",
        "archive": "archived",
    }
    old_status = workflow.status
    new_status = mapping.get(action, old_status)
    if action != "comment":
        _apply_related_decision(workflow, action, actor, note)
        workflow.status = new_status
        if new_status in {"approved", "rejected", "archived"}:
            workflow.resolved_at = timezone.now()
            workflow.resolution_note = note
        elif new_status in {"review", "returned"}:
            workflow.resolved_at = None
        workflow.save(update_fields=["status", "resolved_at", "resolution_note", "updated_at"])
    add_workflow_action(workflow, actor, action, note, old_status, new_status)
    return old_status, new_status
