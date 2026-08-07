from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import (
    LearningAPIToken,
    LearningAccount,
    LearningAuditEvent,
    LearningEmailVerificationRequest,
    LearningRateLimitBucket,
)


def _opaque_hash(namespace: str, raw_value: str) -> str:
    return salted_hmac(
        f"opal-learning-{namespace}",
        raw_value,
        secret=settings.SECRET_KEY,
        algorithm="sha256",
    ).hexdigest()


def _rate_key(action: str, identifier: str, window_started_at) -> str:
    raw = f"{action}|{identifier}|{window_started_at.isoformat()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@transaction.atomic
def consume_rate_limit(action: str, identifier: str, *, limit: int, window_seconds: int = 60):
    """Consume one request from a database-backed fixed window.

    This intentionally uses the canonical database so rate limits remain valid across
    PythonAnywhere web workers. It returns the remaining count and reset timestamp.
    """
    now = timezone.now()
    epoch = int(now.timestamp())
    window_epoch = epoch - (epoch % max(1, int(window_seconds)))
    window_started_at = datetime.fromtimestamp(window_epoch, tz=dt_timezone.utc)
    key_hash = _rate_key(action, identifier or "anonymous", window_started_at)
    try:
        bucket, _created = LearningRateLimitBucket.objects.select_for_update().get_or_create(
            key_hash=key_hash,
            defaults={
                "action": action[:40],
                "window_started_at": window_started_at,
                "count": 0,
            },
        )
    except IntegrityError:
        bucket = LearningRateLimitBucket.objects.select_for_update().get(key_hash=key_hash)
    if bucket.count >= limit:
        reset_at = window_started_at + timedelta(seconds=window_seconds)
        raise ValidationError(
            f"تم تجاوز عدد المحاولات المسموح. أعد المحاولة بعد {max(1, int((reset_at-now).total_seconds()))} ثانية."
        )
    bucket.count += 1
    bucket.save(update_fields=["count", "updated_at"])
    return {
        "remaining": max(0, limit - bucket.count),
        "reset_at": window_started_at + timedelta(seconds=window_seconds),
    }


def account_is_locked(account, *, at=None):
    moment = at or timezone.now()
    return bool(account.locked_until and account.locked_until > moment)


@transaction.atomic
def record_login_failure(account):
    if account is None:
        return None
    locked = LearningAccount.objects.select_for_update().get(pk=account.pk)
    now = timezone.now()
    if locked.locked_until and locked.locked_until <= now:
        locked.failed_login_count = 0
        locked.locked_until = None
    locked.failed_login_count += 1
    max_attempts = int(getattr(settings, "OPAL_LEARNING_LOGIN_MAX_ATTEMPTS", 5))
    if locked.failed_login_count >= max_attempts:
        minutes = int(getattr(settings, "OPAL_LEARNING_LOGIN_LOCK_MINUTES", 15))
        locked.locked_until = now + timedelta(minutes=minutes)
    locked.save(update_fields=["failed_login_count", "locked_until", "updated_at"])
    return locked


@transaction.atomic
def record_login_success(account):
    locked = LearningAccount.objects.select_for_update().get(pk=account.pk)
    if locked.failed_login_count or locked.locked_until:
        locked.failed_login_count = 0
        locked.locked_until = None
        locked.save(update_fields=["failed_login_count", "locked_until", "updated_at"])
    return locked


@transaction.atomic
def create_email_verification_request(account, *, ip_address=None):
    now = timezone.now()
    minutes = int(getattr(settings, "OPAL_LEARNING_EMAIL_VERIFICATION_MINUTES", 1440))
    LearningEmailVerificationRequest.objects.filter(
        account=account,
        used_at__isnull=True,
        expires_at__gt=now,
    ).update(used_at=now)
    raw_token = secrets.token_urlsafe(32)
    request_row = LearningEmailVerificationRequest.objects.create(
        account=account,
        token_hash=_opaque_hash("email-verification", raw_token),
        expires_at=now + timedelta(minutes=minutes),
        request_ip=ip_address,
    )
    return request_row, raw_token


def deliver_email_verification(request_row, raw_token, verify_url):
    if not getattr(settings, "OPAL_LEARNING_EMAIL_ENABLED", False):
        request_row.delivery_status = "failed"
        request_row.delivery_error = "إرسال البريد غير مهيأ في إعدادات البيئة."
        request_row.save(update_fields=["delivery_status", "delivery_error"])
        return False
    try:
        sent = send_mail(
            "توثيق البريد — منصة أوبال التعليمية",
            (
                f"مرحبًا {request_row.account.full_name}،\n\n"
                "وثّق بريدك الإلكتروني لتمكين جميع وظائف الحساب والاشتراكات:\n"
                f"{verify_url}\n\n"
                "إذا لم تنشئ هذا الحساب، تجاهل الرسالة."
            ),
            getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@opal-learning.local"),
            [request_row.account.email],
            fail_silently=False,
        )
        if sent != 1:
            raise RuntimeError("لم يقبل مزود البريد الرسالة.")
    except Exception as exc:
        request_row.delivery_status = "failed"
        request_row.delivery_error = str(exc)[:240]
        request_row.save(update_fields=["delivery_status", "delivery_error"])
        return False
    request_row.delivery_status = "sent"
    request_row.delivery_error = ""
    request_row.save(update_fields=["delivery_status", "delivery_error"])
    return True


def find_valid_email_verification(raw_token):
    if not raw_token:
        return None
    return (
        LearningEmailVerificationRequest.objects.select_related("account")
        .filter(
            token_hash=_opaque_hash("email-verification", raw_token),
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
            account__is_active=True,
        )
        .first()
    )


@transaction.atomic
def complete_email_verification(request_row, *, ip_address=None):
    locked = (
        LearningEmailVerificationRequest.objects.select_for_update()
        .select_related("account")
        .get(pk=request_row.pk)
    )
    now = timezone.now()
    if locked.used_at is not None or locked.expires_at <= now or not locked.account.is_active:
        raise ValidationError("رابط توثيق البريد منتهي أو مستخدم سابقًا.")
    account = LearningAccount.objects.select_for_update().get(pk=locked.account_id)
    account.email_verified_at = account.email_verified_at or now
    account.save(update_fields=["email_verified_at", "updated_at"])
    locked.used_at = now
    locked.save(update_fields=["used_at"])
    LearningEmailVerificationRequest.objects.filter(
        account=account, used_at__isnull=True
    ).exclude(pk=locked.pk).update(used_at=now)
    LearningAuditEvent.objects.create(
        account=account,
        action="email_verified",
        entity_type="learning_account",
        entity_id=str(account.pk),
        ip_address=ip_address,
    )
    return account


def email_verification_required(account):
    return bool(
        getattr(settings, "OPAL_LEARNING_REQUIRE_EMAIL_VERIFICATION", True)
        and account.email_verified_at is None
    )


@transaction.atomic
def issue_api_token(account, *, device_name="", ip_address=None):
    if account.role == LearningAccount.Role.MANAGER:
        raise ValidationError("مدير OPAL ERP لا يستخدم رموز API الخاصة بمستخدمي المنصة.")
    if email_verification_required(account):
        raise ValidationError("وثّق بريدك الإلكتروني قبل تسجيل جهاز جديد.")
    raw_token = "olp_" + secrets.token_urlsafe(36)
    days = int(getattr(settings, "OPAL_LEARNING_API_TOKEN_DAYS", 30))
    token = LearningAPIToken.objects.create(
        account=account,
        token_hash=_opaque_hash("api-token", raw_token),
        token_prefix=raw_token[:12],
        device_name=(device_name or "").strip()[:120],
        expires_at=timezone.now() + timedelta(days=days),
    )
    LearningAuditEvent.objects.create(
        account=account,
        action="api_token_issued",
        entity_type="learning_api_token",
        entity_id=str(token.pk),
        ip_address=ip_address,
        metadata={"device_name": token.device_name},
    )
    return token, raw_token


def find_api_token(raw_token):
    if not raw_token or not raw_token.startswith("olp_"):
        return None
    token_hash = _opaque_hash("api-token", raw_token)
    token = (
        LearningAPIToken.objects.select_related("account")
        .filter(
            token_hash=token_hash,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
            account__is_active=True,
        )
        .first()
    )
    if token is not None and not constant_time_compare(token.token_hash, token_hash):
        return None
    return token


@transaction.atomic
def touch_api_token(token):
    now = timezone.now()
    LearningAPIToken.objects.filter(pk=token.pk).update(last_used_at=now)
    token.last_used_at = now
    return token


@transaction.atomic
def revoke_api_token(token, *, ip_address=None):
    locked = LearningAPIToken.objects.select_for_update().get(pk=token.pk)
    if locked.revoked_at is None:
        locked.revoked_at = timezone.now()
        locked.save(update_fields=["revoked_at"])
        LearningAuditEvent.objects.create(
            account=locked.account,
            action="api_token_revoked",
            entity_type="learning_api_token",
            entity_id=str(locked.pk),
            ip_address=ip_address,
        )
    return locked
