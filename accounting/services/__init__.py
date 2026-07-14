from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from enterprise_ops.models import WorkflowRequest
from enterprise_ops.services import add_workflow_action, notify, notify_management

from ..models import DiscountRequest


@transaction.atomic
def create_discount_workflow(discount_request, user):
    workflow = WorkflowRequest.objects.create(
        request_type="discount",
        title=f"طلب خصم للطالب {discount_request.invoice.student.full_name}",
        description=f"قيمة الخصم المطلوبة: {discount_request.requested_amount}\nالسبب: {discount_request.reason}",
        requester=user,
        related_app="accounting",
        related_model="DiscountRequest",
        related_object_id=str(discount_request.pk),
        priority="normal",
    )
    add_workflow_action(workflow, user, "submit", "إنشاء طلب خصم", "", "new")
    notify_management("طلب خصم جديد", workflow.title, "warning", workflow.get_absolute_url(), exclude_user=user)
    return workflow


@transaction.atomic
def decide_discount(discount_request, user, approve, note=""):
    if discount_request.status != "pending":
        raise ValidationError("تم اتخاذ قرار سابق على هذا الطلب.")
    discount_request.status = "approved" if approve else "rejected"
    discount_request.decided_by = user
    discount_request.decided_at = timezone.now()
    discount_request.decision_note = note
    discount_request.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])
    if approve:
        invoice = discount_request.invoice
        invoice.discount_amount = discount_request.requested_amount
        invoice.full_clean()
        invoice.save(update_fields=["discount_amount", "updated_at"])
        invoice.sync_status()
    if discount_request.requested_by:
        notify(
            discount_request.requested_by,
            "قرار طلب الخصم",
            f"تم {'اعتماد' if approve else 'رفض'} طلب الخصم للطالب {discount_request.invoice.student.full_name}.",
            "success" if approve else "danger",
            "/accounting/discounts/",
        )
    return discount_request
