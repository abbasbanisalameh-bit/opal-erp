from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.utils import timezone

from core.models import AuditLog

from .models import ApprovalAction, Notification


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
