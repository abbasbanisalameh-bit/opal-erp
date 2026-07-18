from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models import AuditLog

from .models import ApprovalAction, Notification


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


def audit(request, action, model_name="", object_id="", description=""):
    return AuditLog.objects.create(
        user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
        action=action,
        model_name=model_name,
        object_id=str(object_id or ""),
        description=description,
        ip_address=client_ip(request),
    )


def notify(recipient, title, message="", level="info", link="", event_key=""):
    if not recipient:
        return None
    values = {"title": title, "message": message, "level": level, "link": link}
    if event_key:
        item, created = Notification.objects.get_or_create(
            recipient=recipient,
            event_key=event_key,
            defaults=values,
        )
        return item
    return Notification.objects.create(recipient=recipient, **values)


def notify_management(title, message="", level="info", link="", exclude_user=None):
    qs = User.objects.filter(is_active=True).filter(is_staff=True)
    if exclude_user:
        qs = qs.exclude(pk=exclude_user.pk)
    return [notify(user, title, message, level, link) for user in qs]


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
