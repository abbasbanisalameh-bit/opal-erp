from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from decimal import Decimal, InvalidOperation
from urllib import error as urlerror
from urllib import request as urlrequest

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .card_codes import generate_unique_card_code
from .models import (
    LearningAccount,
    LearningAuditEvent,
    LearningPaymentEvent,
    LearningPaymentOrder,
    LearningSubscriptionCard,
    LearningSubscriptionPlan,
)
from .services import create_learning_notification


def payment_configuration_status():
    enabled = bool(getattr(settings, "OPAL_LEARNING_PAYMENT_ENABLED", False))
    provider = (getattr(settings, "OPAL_LEARNING_PAYMENT_PROVIDER", "manual") or "manual").strip()
    checkout_url = (getattr(settings, "OPAL_LEARNING_PAYMENT_CHECKOUT_URL", "") or "").strip()
    api_key = (getattr(settings, "OPAL_LEARNING_PAYMENT_API_KEY", "") or "").strip()
    webhook_secret = (getattr(settings, "OPAL_LEARNING_PAYMENT_WEBHOOK_SECRET", "") or "").strip()
    external = provider != "manual"
    configured = enabled and (
        (not external and bool(getattr(settings, "OPAL_LEARNING_MANUAL_PAYMENT_ALLOWED", True)))
        or (external and checkout_url.startswith("https://") and bool(api_key) and bool(webhook_secret))
    )
    return {
        "enabled": enabled,
        "provider": provider,
        "external": external,
        "configured": configured,
        "checkout_url": checkout_url,
        "has_api_key": bool(api_key),
        "has_webhook_secret": bool(webhook_secret),
        "currency": getattr(settings, "OPAL_LEARNING_PAYMENT_CURRENCY", "JOD"),
        "manual_allowed": bool(getattr(settings, "OPAL_LEARNING_MANUAL_PAYMENT_ALLOWED", True)),
    }


def _order_public_id():
    return "PAY-" + secrets.token_hex(10).upper()


@transaction.atomic
def create_payment_order(learner, plan, *, idempotency_key=None, metadata=None):
    if learner.role != LearningAccount.Role.LEARNER or not learner.is_active:
        raise ValidationError("طلب الاشتراك متاح لحساب متعلم فعال فقط.")
    if not plan.is_active:
        raise ValidationError("خطة الاشتراك غير متاحة حاليًا.")
    key = (idempotency_key or secrets.token_urlsafe(24))[:80]
    existing = LearningPaymentOrder.objects.filter(idempotency_key=key).first()
    if existing:
        if existing.learner_id != learner.pk or existing.plan_id != plan.pk:
            raise ValidationError("مفتاح منع التكرار مستخدم لطلب مختلف.")
        return existing, False
    order = LearningPaymentOrder.objects.create(
        public_id=_order_public_id(),
        learner=learner,
        plan=plan,
        amount=plan.price,
        currency=plan.currency,
        provider=getattr(settings, "OPAL_LEARNING_PAYMENT_PROVIDER", "manual") or "manual",
        idempotency_key=key,
        metadata=metadata or {},
    )
    LearningAuditEvent.objects.create(
        account=learner,
        action="payment_order_created",
        entity_type="learning_payment_order",
        entity_id=str(order.pk),
        metadata={"public_id": order.public_id, "plan_id": plan.pk, "amount": str(order.amount)},
    )
    return order, True


def initiate_external_checkout(order, *, return_url, webhook_url):
    status = payment_configuration_status()
    if not status["configured"] or not status["external"]:
        return order
    payload = {
        "merchant_order_id": order.public_id,
        "amount": str(order.amount),
        "currency": order.currency,
        "description": order.plan.name,
        "customer": {
            "name": order.learner.full_name,
            "email": order.learner.email,
            "phone": order.learner.phone,
        },
        "return_url": return_url,
        "webhook_url": webhook_url,
    }
    req = urlrequest.Request(
        status["checkout_url"],
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {getattr(settings, 'OPAL_LEARNING_PAYMENT_API_KEY', '')}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Idempotency-Key": order.idempotency_key,
        },
        method="POST",
    )
    try:
        with urlrequest.urlopen(
            req,
            timeout=int(getattr(settings, "OPAL_LEARNING_PAYMENT_TIMEOUT", 20)),
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urlerror.URLError, urlerror.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        order.status = LearningPaymentOrder.Status.FAILED
        order.failure_reason = f"تعذر إنشاء جلسة الدفع: {exc}"[:500]
        order.save(update_fields=["status", "failure_reason", "updated_at"])
        raise ValidationError("تعذر الاتصال ببوابة الدفع. لم يُخصم أي مبلغ.") from exc
    checkout_url = (data.get("checkout_url") or "").strip()
    provider_reference = str(data.get("reference") or data.get("id") or "").strip()
    if not checkout_url.startswith("https://") or not provider_reference:
        order.status = LearningPaymentOrder.Status.FAILED
        order.failure_reason = "استجابة بوابة الدفع غير مكتملة."
        order.save(update_fields=["status", "failure_reason", "updated_at"])
        raise ValidationError("أعادت بوابة الدفع استجابة غير صالحة.")
    order.status = LearningPaymentOrder.Status.PROCESSING
    order.checkout_url = checkout_url[:1000]
    order.provider_reference = provider_reference[:160]
    order.save(
        update_fields=["status", "checkout_url", "provider_reference", "updated_at"]
    )
    return order


def _new_card_code(order):
    # Keep payment/order identifiers private: the public card value is fully random.
    return generate_unique_card_code(prefix="OPAL")


@transaction.atomic
def mark_order_paid(order, *, provider_reference="", event_id="", manager_label=""):
    locked = (
        LearningPaymentOrder.objects.select_for_update()
        .select_related("learner", "plan")
        .prefetch_related("plan__subjects")
        .get(pk=order.pk)
    )
    if locked.status == LearningPaymentOrder.Status.PAID:
        return locked
    if locked.status in {
        LearningPaymentOrder.Status.CANCELLED,
        LearningPaymentOrder.Status.REFUNDED,
    }:
        raise ValidationError("لا يمكن اعتماد طلب ملغي أو مسترد كمدفوع.")
    card = LearningSubscriptionCard.objects.create(
        code=_new_card_code(locked),
        duration=locked.plan.duration,
        grants_all_subjects=locked.plan.grants_all_subjects,
    )
    if not locked.plan.grants_all_subjects:
        card.subjects.set(locked.plan.subjects.all())
    card.activate(locked.learner)
    locked.status = LearningPaymentOrder.Status.PAID
    locked.paid_at = timezone.now()
    locked.provider_reference = (provider_reference or locked.provider_reference)[:160]
    locked.subscription_card = card
    locked.failure_reason = ""
    locked.save(
        update_fields=[
            "status",
            "paid_at",
            "provider_reference",
            "subscription_card",
            "failure_reason",
            "updated_at",
        ]
    )
    LearningAuditEvent.objects.create(
        account=locked.learner,
        action="payment_order_paid",
        entity_type="learning_payment_order",
        entity_id=str(locked.pk),
        metadata={
            "public_id": locked.public_id,
            "provider_reference": locked.provider_reference,
            "event_id": event_id,
            "manager_label": manager_label,
        },
    )
    create_learning_notification(
        locked.learner,
        notification_type="subscription",
        title="تم تفعيل اشتراكك",
        body=f"تم اعتماد دفع خطة {locked.plan.name} وتفعيل اشتراكك حتى {timezone.localtime(card.expires_at):%Y-%m-%d}.",
        action_url=reverse("learning_platform:subscriptions"),
        dedupe_key=f"payment-paid:{locked.pk}",
    )
    return locked


@transaction.atomic
def mark_order_refunded(order, *, provider_reference="", event_id="", reason=""):
    locked = (
        LearningPaymentOrder.objects.select_for_update()
        .select_related("learner", "plan", "subscription_card")
        .get(pk=order.pk)
    )
    if locked.status == LearningPaymentOrder.Status.REFUNDED:
        return locked
    if locked.status != LearningPaymentOrder.Status.PAID:
        raise ValidationError("لا يمكن استرداد طلب لم يُعتمد كمدفوع.")
    card = locked.subscription_card
    if card is not None and card.status != LearningSubscriptionCard.Status.CANCELLED:
        card.status = LearningSubscriptionCard.Status.CANCELLED
        if card.expires_at is None or card.expires_at > timezone.now():
            card.expires_at = timezone.now()
        card.save(update_fields=["status", "expires_at"])
    locked.status = LearningPaymentOrder.Status.REFUNDED
    locked.provider_reference = (provider_reference or locked.provider_reference)[:160]
    locked.failure_reason = (reason or "تم استرداد عملية الدفع.")[:500]
    locked.save(update_fields=["status", "provider_reference", "failure_reason", "updated_at"])
    LearningAuditEvent.objects.create(
        account=locked.learner,
        action="payment_order_refunded",
        entity_type="learning_payment_order",
        entity_id=str(locked.pk),
        metadata={
            "public_id": locked.public_id,
            "provider_reference": locked.provider_reference,
            "event_id": event_id,
        },
    )
    create_learning_notification(
        locked.learner,
        notification_type="subscription",
        title="تم استرداد عملية الاشتراك",
        body=f"تم تسجيل استرداد خطة {locked.plan.name} وإيقاف الوصول المرتبط بها.",
        action_url=reverse("learning_platform:subscriptions"),
        dedupe_key=f"payment-refunded:{locked.pk}",
    )
    return locked


@transaction.atomic
def cancel_payment_order(order, *, reason=""):
    locked = LearningPaymentOrder.objects.select_for_update().get(pk=order.pk)
    if locked.status == LearningPaymentOrder.Status.PAID:
        raise ValidationError("لا يمكن إلغاء طلب مدفوع؛ استخدم مسار الاسترداد المعتمد.")
    if locked.status not in {
        LearningPaymentOrder.Status.CANCELLED,
        LearningPaymentOrder.Status.REFUNDED,
    }:
        locked.status = LearningPaymentOrder.Status.CANCELLED
        locked.cancelled_at = timezone.now()
        locked.failure_reason = reason[:500]
        locked.save(
            update_fields=["status", "cancelled_at", "failure_reason", "updated_at"]
        )
    return locked


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    secret = (getattr(settings, "OPAL_LEARNING_PAYMENT_WEBHOOK_SECRET", "") or "").encode("utf-8")
    if not secret or not signature:
        return False
    expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    cleaned = signature.removeprefix("sha256=").strip().lower()
    return hmac.compare_digest(expected, cleaned)


@transaction.atomic
def process_payment_webhook(raw_body: bytes, signature: str):
    if not verify_webhook_signature(raw_body, signature):
        raise ValidationError("توقيع إشعار بوابة الدفع غير صحيح.")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("حمولة إشعار الدفع غير صالحة.") from exc
    event_id = str(payload.get("event_id") or payload.get("id") or "").strip()
    event_type = str(payload.get("event_type") or payload.get("type") or "").strip().lower()
    public_id = str(payload.get("merchant_order_id") or payload.get("order_id") or "").strip()
    provider_reference = str(payload.get("reference") or payload.get("payment_id") or "").strip()
    raw_amount = payload.get("amount")
    event_currency = str(payload.get("currency") or "").strip().upper()
    if not event_id or not public_id or not event_type:
        raise ValidationError("إشعار الدفع يفتقد المعرفات المطلوبة.")
    order = LearningPaymentOrder.objects.select_for_update().filter(public_id=public_id).first()
    if order is None:
        raise ValidationError("طلب الدفع المشار إليه غير موجود.")
    if event_type in {"paid", "payment.paid", "payment_succeeded", "succeeded"}:
        if raw_amount is None or not event_currency:
            raise ValidationError("إشعار الدفع الناجح يجب أن يتضمن المبلغ والعملة.")
        try:
            event_amount = Decimal(str(raw_amount)).quantize(Decimal("0.001"))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValidationError("مبلغ إشعار الدفع غير صالح.") from exc
        if event_amount != order.amount or event_currency != order.currency.upper():
            raise ValidationError("مبلغ أو عملة إشعار الدفع لا يطابقان طلب الاشتراك.")
    payload_hash = hashlib.sha256(raw_body).hexdigest()
    event, created = LearningPaymentEvent.objects.get_or_create(
        provider_event_id=event_id[:180],
        defaults={
            "order": order,
            "event_type": event_type[:80],
            "signature_valid": True,
            "payload_hash": payload_hash,
            "payload": payload,
        },
    )
    if not created:
        if event.payload_hash != payload_hash:
            raise ValidationError("أعيد استخدام معرف حدث الدفع بحمولة مختلفة.")
        return order, event, False
    if event_type in {"paid", "payment.paid", "payment_succeeded", "succeeded"}:
        order = mark_order_paid(
            order,
            provider_reference=provider_reference,
            event_id=event_id,
        )
    elif event_type in {"failed", "payment.failed", "payment_failed"}:
        order.status = LearningPaymentOrder.Status.FAILED
        order.failure_reason = str(payload.get("reason") or "رفضت بوابة الدفع العملية.")[:500]
        order.save(update_fields=["status", "failure_reason", "updated_at"])
    elif event_type in {"cancelled", "payment.cancelled", "canceled"}:
        order = cancel_payment_order(order, reason="ألغيت العملية لدى بوابة الدفع.")
    elif event_type in {"refunded", "payment.refunded", "refund.succeeded", "chargeback"}:
        order = mark_order_refunded(
            order,
            provider_reference=provider_reference,
            event_id=event_id,
            reason=str(payload.get("reason") or "تم الاسترداد لدى بوابة الدفع."),
        )
    event.processed_at = timezone.now()
    event.save(update_fields=["processed_at"])
    return order, event, True
