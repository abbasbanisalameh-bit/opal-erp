from __future__ import annotations

import json
import os
from datetime import datetime, timezone as dt_timezone
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from .models import LearningCourse, LearningSubscriptionPlan
from .payment_services import payment_configuration_status


def _check(code, label, status, detail, *, blocking=False):
    return {
        "code": code,
        "label": label,
        "status": status,
        "detail": detail,
        "blocking": bool(blocking),
    }


def collect_learning_readiness_checks(*, include_migrations=True):
    checks = []
    public_launch = bool(getattr(settings, "OPAL_LEARNING_PUBLIC_LAUNCH", False))
    checks.append(
        _check(
            "public_launch",
            "قفل الإطلاق العام",
            "pass" if public_launch else "warn",
            "قفل الإطلاق العام مفتوح صراحة." if public_launch else "الإطلاق العام مقفل؛ هذا مناسب للتجربة المحدودة فقط.",
            blocking=False,
        )
    )
    debug = bool(settings.DEBUG)
    checks.append(
        _check(
            "debug",
            "وضع التصحيح",
            "fail" if debug else "pass",
            "DEBUG يجب أن يكون False في التشغيل الفعلي." if debug else "DEBUG=False.",
            blocking=True,
        )
    )
    hosts = list(getattr(settings, "ALLOWED_HOSTS", []))
    unsafe_hosts = not hosts or "*" in hosts
    checks.append(
        _check(
            "allowed_hosts",
            "النطاقات المسموحة",
            "fail" if unsafe_hosts else "pass",
            "حدد نطاق الموقع صراحة ولا تستخدم *." if unsafe_hosts else "ALLOWED_HOSTS محددة.",
            blocking=True,
        )
    )
    cookie_secure = bool(getattr(settings, "SESSION_COOKIE_SECURE", False)) and bool(
        getattr(settings, "CSRF_COOKIE_SECURE", False)
    )
    checks.append(
        _check(
            "secure_cookies",
            "كوكيز الجلسة وCSRF",
            "pass" if cookie_secure else "fail",
            "الكوكيز الآمنة مفعلة." if cookie_secure else "فعّل SESSION_COOKIE_SECURE وCSRF_COOKIE_SECURE.",
            blocking=True,
        )
    )
    email_enabled = bool(getattr(settings, "OPAL_LEARNING_EMAIL_ENABLED", False))
    email_complete = all(
        [
            getattr(settings, "EMAIL_HOST", ""),
            getattr(settings, "EMAIL_HOST_USER", ""),
            getattr(settings, "EMAIL_HOST_PASSWORD", ""),
            getattr(settings, "DEFAULT_FROM_EMAIL", ""),
        ]
    )
    email_ready = email_enabled and email_complete
    checks.append(
        _check(
            "email",
            "البريد واستعادة الحساب",
            "pass" if email_ready else ("fail" if public_launch else "warn"),
            "إعداد SMTP مكتمل." if email_ready else "هيئ SMTP ومرسلًا موثقًا قبل الإطلاق العام؛ الاستعادة الإدارية فقط متاحة في التجربة.",
            blocking=public_launch,
        )
    )
    payment = payment_configuration_status()
    payment_ready = payment["configured"] and (payment["external"] if public_launch else True)
    checks.append(
        _check(
            "payment",
            "بوابة الدفع",
            "pass" if payment_ready else ("fail" if public_launch else "warn"),
            (
                f"مزود الدفع الخارجي {payment['provider']} مهيأ."
                if payment_ready and payment["external"]
                else "التحصيل اليدوي مهيأ للتشغيل الداخلي فقط."
                if payment["configured"] and not payment["external"]
                else "لم تُهيأ بوابة دفع فعلية أو وضع التحصيل اليدوي المعتمد."
            ),
            blocking=public_launch,
        )
    )
    plans_count = LearningSubscriptionPlan.objects.filter(is_active=True).count()
    checks.append(
        _check(
            "plans",
            "خطط الاشتراك",
            "pass" if plans_count else "fail",
            f"عدد الخطط الفعالة: {plans_count}." if plans_count else "أنشئ خطة اشتراك فعالة واحدة على الأقل.",
            blocking=True,
        )
    )
    courses_count = LearningCourse.objects.filter(status=LearningCourse.Status.PUBLISHED).count()
    checks.append(
        _check(
            "published_content",
            "المحتوى المنشور",
            "pass" if courses_count else "warn",
            f"عدد الدورات المنشورة: {courses_count}." if courses_count else "لا توجد دورة منشورة لاختبار القبول.",
        )
    )
    lock_path = Path(settings.BASE_DIR) / "requirements-lock-r20.txt"
    lock_ready = False
    if lock_path.is_file():
        try:
            lock_text = lock_path.read_text(encoding="utf-8")
            lock_ready = "Django==" in lock_text and "Pillow==" in lock_text
        except OSError:
            lock_ready = False
    checks.append(
        _check(
            "dependency_lock",
            "قفل الاعتماديات",
            "pass" if lock_ready else ("fail" if public_launch else "warn"),
            "ملف requirements-lock-r20.txt موجود ويثبت البيئة المختبرة." if lock_ready else "أنشئ requirements-lock-r20.txt من البيئة التي نجحت فيها الاختبارات قبل الإطلاق العام.",
            blocking=public_launch,
        )
    )
    backend = connection.vendor
    checks.append(
        _check(
            "database",
            "قاعدة البيانات",
            "warn" if backend == "sqlite" else "pass",
            (
                "SQLite مناسبة للتجربة والحمل المحدود فقط؛ اختبر التزامن أو انتقل إلى PostgreSQL للإطلاق الواسع."
                if backend == "sqlite"
                else f"قاعدة البيانات: {backend}."
            ),
        )
    )
    media_root = Path(getattr(settings, "MEDIA_ROOT", settings.BASE_DIR / "media"))
    try:
        media_root.mkdir(parents=True, exist_ok=True)
        writable = os.access(media_root, os.W_OK)
    except OSError:
        writable = False
    checks.append(
        _check(
            "media_storage",
            "تخزين الملفات",
            "pass" if writable else "fail",
            "مسار الوسائط قابل للكتابة." if writable else "مسار الوسائط غير قابل للكتابة.",
            blocking=True,
        )
    )
    backup_dir = getattr(settings, "OPAL_LEARNING_BACKUP_DIR", "") or str(
        Path(settings.BASE_DIR) / "backups" / "learning_platform"
    )
    backup_path = Path(backup_dir)
    try:
        backup_path.mkdir(parents=True, exist_ok=True)
        backup_writable = os.access(backup_path, os.W_OK)
    except OSError:
        backup_writable = False
    checks.append(
        _check(
            "backup_directory",
            "مسار النسخ الاحتياطي",
            "pass" if backup_writable else "fail",
            f"المسار: {backup_path}" if backup_writable else "تعذر إنشاء أو الكتابة في مسار النسخ.",
            blocking=True,
        )
    )
    verified_markers = sorted(backup_path.glob("*.zip.verified.json"), key=lambda item: item.stat().st_mtime, reverse=True) if backup_writable else []
    latest_verified_at = None
    if verified_markers:
        try:
            marker_payload = json.loads(verified_markers[0].read_text(encoding="utf-8"))
            latest_verified_at = datetime.fromisoformat(str(marker_payload.get("verified_at") or ""))
            if latest_verified_at.tzinfo is None:
                latest_verified_at = latest_verified_at.replace(tzinfo=dt_timezone.utc)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            latest_verified_at = None
    max_backup_age_hours = int(getattr(settings, "OPAL_LEARNING_BACKUP_MAX_AGE_HOURS", 168))
    backup_recent = bool(
        latest_verified_at
        and (datetime.now(dt_timezone.utc) - latest_verified_at.astimezone(dt_timezone.utc)).total_seconds()
        <= max_backup_age_hours * 3600
    )
    checks.append(
        _check(
            "verified_backup",
            "نسخة احتياطية متحققة",
            "pass" if backup_recent else "fail",
            (
                f"آخر تحقق بنيوي: {latest_verified_at.isoformat()}. يجب أيضًا تنفيذ استعادة تجريبية معزولة قبل الإطلاق."
                if backup_recent
                else f"أنشئ نسخة وشغّل verify_learning_backup خلال آخر {max_backup_age_hours} ساعة."
            ),
            blocking=True,
        )
    )
    if include_migrations:
        try:
            executor = MigrationExecutor(connection)
            pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
            migration_ok = not pending
            detail = "لا توجد هجرات معلقة." if migration_ok else f"هجرات معلقة: {len(pending)}."
        except Exception as exc:
            migration_ok = False
            detail = f"تعذر فحص الهجرات: {exc}"
        checks.append(
            _check(
                "migrations",
                "الهجرات",
                "pass" if migration_ok else "fail",
                detail,
                blocking=True,
            )
        )
    ai_external_enabled = bool(getattr(settings, "OPAL_LEARNING_AI_PROVIDER_ENABLED", False))
    ai_configured = all(
        [
            getattr(settings, "OPAL_LEARNING_AI_BASE_URL", ""),
            getattr(settings, "OPAL_LEARNING_AI_API_KEY", ""),
            getattr(settings, "OPAL_LEARNING_AI_MODEL", ""),
        ]
    )
    checks.append(
        _check(
            "ai_provider",
            "مزود الذكاء الاصطناعي",
            "pass" if (not ai_external_enabled or ai_configured) else "fail",
            (
                "الوضع المرجعي المحلي مفعّل؛ المزود الخارجي غير مطلوب."
                if not ai_external_enabled
                else "إعداد المزود الخارجي مكتمل."
                if ai_configured
                else "المزود الخارجي مفعّل لكن بياناته ناقصة."
            ),
            blocking=ai_external_enabled,
        )
    )
    failures = [item for item in checks if item["status"] == "fail" and item["blocking"]]
    warnings = [item for item in checks if item["status"] == "warn"]
    if failures:
        overall = "not_ready"
    elif warnings:
        overall = "pilot_ready"
    else:
        overall = "production_ready"
    return {
        "overall": overall,
        "checks": checks,
        "blocking_failures": len(failures),
        "warnings": len(warnings),
    }


def run_django_system_check():
    """Return the framework check output without hiding failures."""
    from io import StringIO

    output = StringIO()
    call_command("check", stdout=output, stderr=output)
    return output.getvalue().strip()
