from datetime import timedelta
import logging

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from core.models import AuditLog

from .models import ApprovalAction, FeedbackTicket, MonthlyServiceEvaluation, Notification


logger = logging.getLogger(__name__)


def feedback_satisfaction_snapshot(queryset=None, today=None, school=None):
    """Return school-scoped satisfaction metrics from persisted evaluations.

    One ``MonthlyServiceEvaluation`` row is one participation even when the
    guardian submitted both rating fields.  Category distributions still count
    their own rating observations.  The "both positive" indicator is the true
    share of paired submissions where both scores are at least four.
    """
    del queryset
    today = today or timezone.localdate()
    recent_start = today - timedelta(days=29)
    previous_start = recent_start - timedelta(days=30)

    base = MonthlyServiceEvaluation.objects.all()
    if school is not None:
        base = base.filter(
            Q(school=school)
            | Q(school__isnull=True, user__profile__school=school)
            | Q(school__isnull=True, user__teacher_profile__school=school)
            | Q(school__isnull=True, user__family_account__school=school)
        ).distinct()

    def submitted_period_q(field, start, end=None):
        query = Q(**{f"{field}__date__gte": start}) | Q(
            **{f"{field}__isnull": True, "created_at__date__gte": start}
        )
        if end is not None:
            query &= (
                Q(**{f"{field}__date__lt": end})
                | Q(**{f"{field}__isnull": True, "created_at__date__lt": end})
            )
        return query

    def rating_metrics(field, submitted_field):
        qs = base.exclude(**{f"{field}__isnull": True})
        recent_q = submitted_period_q(submitted_field, recent_start)
        previous_q = submitted_period_q(submitted_field, previous_start, recent_start)
        metrics = {
            "total": Count("id"),
            "average": Avg(field),
            "positive": Count("id", filter=Q(**{f"{field}__gte": 4})),
            "recent_total": Count("id", filter=recent_q),
            "recent_average": Avg(field, filter=recent_q),
            "previous_total": Count("id", filter=previous_q),
            "previous_average": Avg(field, filter=previous_q),
        }
        for score_value in range(1, 6):
            metrics[f"score_{score_value}"] = Count("id", filter=Q(**{field: score_value}))
        return qs.aggregate(**metrics)

    teaching = rating_metrics("teaching_quality_rating", "teaching_quality_submitted_at")
    electronic = rating_metrics("electronic_services_rating", "electronic_services_submitted_at")
    teaching_total = teaching["total"] or 0
    electronic_total = electronic["total"] or 0
    rating_observations = teaching_total + electronic_total

    participation_qs = base.filter(
        Q(teaching_quality_rating__isnull=False)
        | Q(electronic_services_rating__isnull=False)
    )
    recent_participation_q = (
        Q(teaching_quality_submitted_at__date__gte=recent_start)
        | Q(electronic_services_submitted_at__date__gte=recent_start)
        | Q(
            teaching_quality_submitted_at__isnull=True,
            electronic_services_submitted_at__isnull=True,
            created_at__date__gte=recent_start,
        )
    )
    feedback_total = participation_qs.count()
    feedback_recent_total = participation_qs.filter(recent_participation_q).count()

    paired_qs = base.filter(
        teaching_quality_rating__isnull=False,
        electronic_services_rating__isnull=False,
    )
    paired_total = paired_qs.count()
    both_positive = paired_qs.filter(
        teaching_quality_rating__gte=4,
        electronic_services_rating__gte=4,
    ).count()

    def score(value):
        return round(float(value or 0), 2)

    def percent_from_average(value, count):
        return round((score(value) / 5) * 100, 1) if count else 0

    def positive_percent(value, count):
        return round(((value or 0) / count) * 100, 1) if count else 0

    teaching_average = score(teaching["average"])
    electronic_average = score(electronic["average"])
    weighted_total = teaching_average * teaching_total + electronic_average * electronic_total
    overall_average = round(weighted_total / rating_observations, 2) if rating_observations else 0
    overall_percent = round((overall_average / 5) * 100, 1) if rating_observations else 0

    recent_count = (teaching["recent_total"] or 0) + (electronic["recent_total"] or 0)
    previous_count = (teaching["previous_total"] or 0) + (electronic["previous_total"] or 0)
    recent_weighted = (
        score(teaching["recent_average"]) * (teaching["recent_total"] or 0)
        + score(electronic["recent_average"]) * (electronic["recent_total"] or 0)
    )
    previous_weighted = (
        score(teaching["previous_average"]) * (teaching["previous_total"] or 0)
        + score(electronic["previous_average"]) * (electronic["previous_total"] or 0)
    )
    recent_overall = round(recent_weighted / recent_count, 2) if recent_count else 0
    previous_overall = round(previous_weighted / previous_count, 2) if previous_count else 0
    trend_available = bool(recent_count and previous_count)
    trend_delta = round(recent_overall - previous_overall, 2) if trend_available else 0

    if not rating_observations:
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
        "feedback_data_available": bool(rating_observations),
        "teaching_data_available": bool(teaching_total),
        "electronic_data_available": bool(electronic_total),
        "feedback_total": feedback_total,
        "feedback_rating_observations": rating_observations,
        "feedback_recent_total": feedback_recent_total,
        "teaching_rating_average": teaching_average,
        "electronic_rating_average": electronic_average,
        "overall_rating_average": overall_average,
        "teaching_satisfaction_percent": percent_from_average(teaching["average"], teaching_total),
        "electronic_satisfaction_percent": percent_from_average(electronic["average"], electronic_total),
        "overall_satisfaction_percent": overall_percent,
        "teaching_positive_percent": positive_percent(teaching["positive"], teaching_total),
        "electronic_positive_percent": positive_percent(electronic["positive"], electronic_total),
        "both_positive_percent": round((both_positive / paired_total) * 100, 1) if paired_total else 0,
        "both_positive_total": both_positive,
        "paired_feedback_total": paired_total,
        "teaching_rating_distribution": [teaching[f"score_{value}"] or 0 for value in range(1, 6)],
        "electronic_rating_distribution": [electronic[f"score_{value}"] or 0 for value in range(1, 6)],
        "feedback_teacher_responses": participation_qs.filter(user__teacher_profile__isnull=False).count(),
        "feedback_parent_responses": participation_qs.filter(user__family_account__isnull=False).count(),
        "feedback_recent_overall_average": recent_overall,
        "feedback_trend_available": trend_available,
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
    except Exception:
        logger.exception("تعذر تسجيل حدث التدقيق الثانوي.")
        return None


def visible_notifications_for_user(user):
    """Return the canonical personal-notification stream for ``user``.

    New complaints and suggestions are operational work items for management,
    so their count is shown on the executive dashboard card rather than in the
    personal notification bell.  Historical manager notifications generated
    by older releases are filtered from the visible stream without deleting
    audit data.  Feedback status updates sent back to the original sender keep
    using the normal notification stream.
    """
    qs = user.opal_notifications.all()
    from .permissions import is_management

    if is_management(user):
        qs = qs.exclude(event_key__startswith="feedback:")
    return qs


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
    try:
        if event_key:
            item, _ = Notification.objects.get_or_create(
                recipient=recipient,
                event_key=event_key,
                defaults=values,
            )
            return item
        return Notification.objects.create(recipient=recipient, **values)
    except Exception:
        logger.exception("تعذر إنشاء إشعار ثانوي للمستخدم %s.", getattr(recipient, "pk", None))
        return None


def management_recipients():
    from django.db.models import Q

    return User.objects.filter(is_active=True).filter(
        Q(is_staff=True)
        | Q(is_superuser=True)
        | Q(profile__role__code__in={"super_admin", "school_owner", "principal", "accountant", "secretary"})
    ).distinct()


def notify_management(title, message="", level="info", link="", exclude_user=None, event_key=""):
    qs = management_recipients()
    if exclude_user:
        qs = qs.exclude(pk=exclude_user.pk)
    return [
        notify(user, title, message, level, link, f"{event_key}:user:{user.pk}" if event_key else "")
        for user in qs
    ]


def notify_management_batch(items, *, exclude_user=None):
    """Create many management notifications without query-per-item loops.

    ``notify_management`` remains the canonical helper for a single event.
    Attendance closure can expose dozens of pending registers at once, so this
    companion accepts event dictionaries and performs recipient discovery once,
    existing-event checks once per recipient, then one conflict-safe bulk insert.
    The same per-recipient event-key contract is preserved exactly.
    """
    rows = [
        {
            "title": str(item.get("title") or "")[:180],
            "message": str(item.get("message") or ""),
            "level": str(item.get("level") or "info"),
            "link": str(item.get("link") or "")[:500],
            "event_key": str(item.get("event_key") or "")[:180],
            "sound_enabled": bool(item.get("sound_enabled", True)),
        }
        for item in items
        if item and item.get("event_key")
    ]
    if not rows:
        return 0

    try:
        recipients = management_recipients()
        if exclude_user:
            recipients = recipients.exclude(pk=exclude_user.pk)
        recipient_ids = list(recipients.values_list("pk", flat=True))
        if not recipient_ids:
            return 0

        pending_notifications = []
        for recipient_id in recipient_ids:
            suffix = f":user:{recipient_id}"
            full_keys = [f"{row['event_key'][:180 - len(suffix)]}{suffix}" for row in rows]
            existing_keys = set(
                Notification.objects.filter(
                    recipient_id=recipient_id,
                    event_key__in=full_keys,
                ).values_list("event_key", flat=True)
            )
            for row, full_key in zip(rows, full_keys):
                if full_key in existing_keys:
                    continue
                pending_notifications.append(
                    Notification(
                        recipient_id=recipient_id,
                        title=row["title"],
                        message=row["message"],
                        level=row["level"],
                        link=row["link"],
                        event_key=full_key,
                        sound_enabled=row["sound_enabled"],
                    )
                )

        if not pending_notifications:
            return 0
        Notification.objects.bulk_create(
            pending_notifications,
            batch_size=500,
            ignore_conflicts=True,
        )
        return len(pending_notifications)
    except Exception:
        logger.exception("تعذر إنشاء حزمة إشعارات الإدارة الثانوية.")
        return 0


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
