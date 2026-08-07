"""Request-scoped canonical runtime context for OPAL ERP.

Global template context processors run independently.  Without a shared request
cache they can repeat the same profile, school, and academic-context lookups on
every page.  These helpers keep one authoritative value per HTTP request while
preserving the existing database and business behavior.
"""

from __future__ import annotations

from .academic_context import resolve_academic_context
from .models import School


_UNSET = object()


def _cached(request, name: str, loader):
    value = getattr(request, name, _UNSET)
    if value is _UNSET:
        value = loader()
        setattr(request, name, value)
    return value


def request_profile(request):
    """Return the authenticated user's OPAL profile once per request."""

    def load():
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        return getattr(user, "profile", None)

    return _cached(request, "_opal_runtime_profile", load)


def request_school(request):
    """Resolve the canonical school once per request.

    The resolution order intentionally matches the established OPAL identity
    context: the user's school first, then the first active school.  It does not
    create records and does not introduce a second school-selection rule.
    """

    def load():
        profile = request_profile(request)
        school = getattr(profile, "school", None) if profile else None
        return school or School.objects.filter(is_active=True).first()

    return _cached(request, "_opal_runtime_school", load)


def request_academic_context(request, *, persist: bool = True):
    """Return one academic context for the current request."""

    cache_name = "_opal_runtime_academic_context" if persist else "_opal_runtime_academic_context_readonly"

    def load():
        school = request_school(request)
        return resolve_academic_context(school=school, persist=persist) if school else None

    return _cached(request, cache_name, load)
