from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import Family


def is_parent_user(user):
    """True for non-staff accounts linked to the authoritative Family model."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or user.is_staff:
        return False
    return Family.objects.filter(user=user).exists()


def parent_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not is_parent_user(request.user):
            raise PermissionDenied("هذه الصفحة مخصصة لحسابات أولياء الأمور فقط.")
        return view_func(request, *args, **kwargs)

    return wrapped
