from django.apps import apps
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver


def _ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "") if request else ""
    return (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.META.get("REMOTE_ADDR") if request else None)
    ) or None


def _audit_log_model():
    return apps.get_model("core", "AuditLog")


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    _audit_log_model().objects.create(
        user=user,
        action="login",
        model_name="auth.User",
        object_id=str(user.pk),
        description="تسجيل دخول ناجح",
        ip_address=_ip(request),
    )


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    if user:
        _audit_log_model().objects.create(
            user=user,
            action="logout",
            model_name="auth.User",
            object_id=str(user.pk),
            description="تسجيل خروج",
            ip_address=_ip(request),
        )
