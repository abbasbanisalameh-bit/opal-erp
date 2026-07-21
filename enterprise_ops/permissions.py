from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from accounts.workflow import is_management_user, role_code

from .models import RolePermissionRule


def is_management(user):
    return is_management_user(user)


def management_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not is_management(request.user):
            messages.error(request, "لا تملك صلاحية الوصول إلى هذه الصفحة.")
            return redirect("dashboard:home")
        return view_func(request, *args, **kwargs)
    return wrapped


def superuser_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            messages.error(request, "هذا الإجراء متاح لمدير النظام فقط.")
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
    if feature in {"executive", "approvals"}:
        return is_management(user)
    if feature == "workflow":
        if action == "view":
            return True
        if action == "create":
            return is_management(user) or code in {"teacher", "parent"} or hasattr(user, "teacher_profile") or hasattr(user, "family_account")
        return is_management(user)
    if feature in {"notifications", "audit"}:
        return action == "view"
    if feature == "reports":
        return action in {"view", "export"}
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
