from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def is_teacher_user(user):
    return bool(getattr(user, "is_authenticated", False) and hasattr(user, "teacher_profile") and user.teacher_profile.is_active)


def teacher_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not is_teacher_user(request.user):
            raise PermissionDenied("هذه الصفحة مخصصة للمعلمين.")
        return view(request, *args, **kwargs)
    return wrapped
