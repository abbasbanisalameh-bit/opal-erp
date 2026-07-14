from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .models import RolePermissionRule


def role_code(user):
    try:
        return user.profile.role.code or ""
    except Exception:
        return ""


def is_management(user):
    return bool(user.is_authenticated and (user.is_staff or user.is_superuser or role_code(user) in {"super_admin", "school_owner", "principal", "accountant", "secretary"}))


def management_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not is_management(request.user):
            messages.error(request, "لا تملك صلاحية الوصول إلى هذه الصفحة.")
            return redirect("dashboard:home")
        return view_func(request, *args, **kwargs)
    return wrapped


def has_feature_permission(user, feature, action="view"):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    code = role_code(user)
    field = f"can_{action}"
    rule = RolePermissionRule.objects.filter(role_code=code, feature=feature, is_active=True).first()
    if rule is not None:
        return bool(getattr(rule, field, False))
    if feature in {"executive", "audit", "reports", "approvals"}:
        return is_management(user)
    if feature in {"workflow", "notifications"}:
        return True
    return False


def feature_required(feature, action="view"):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not has_feature_permission(request.user, feature, action):
                messages.error(request, "لا تملك الصلاحية المطلوبة لهذا الإجراء.")
                return redirect("dashboard:home")
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
