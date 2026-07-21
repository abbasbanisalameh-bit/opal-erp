"""OPAL identity, role and access workflow helpers.

This module centralises existing role resolution and account access decisions without
changing the underlying models, permissions matrix, redirects or user experience.
"""
from __future__ import annotations

from django.apps import apps


MANAGEMENT_ROLE_CODES = frozenset(
    {"super_admin", "school_owner", "principal", "accountant", "secretary"}
)
IMPERSONATION_TARGETS = {
    "teacher": ("teachers", "Teacher", "teacher_profile"),
    "parent": ("parent_portal", "Family", "family_account"),
}


def get_user_profile(user):
    """Return the OPAL user profile when available, otherwise ``None``."""
    if not getattr(user, "is_authenticated", False):
        return None
    try:
        return user.profile
    except Exception:
        return None


def role_code(user) -> str:
    """Resolve the canonical OPAL role code for an authenticated user."""
    profile = get_user_profile(user)
    role = getattr(profile, "role", None) if profile is not None else None
    return getattr(role, "code", "") or ""


def is_management_user(user) -> bool:
    """Preserve OPAL's current management-user rule in one place."""
    return bool(
        getattr(user, "is_authenticated", False)
        and (
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or role_code(user) in MANAGEMENT_ROLE_CODES
        )
    )


def can_manage_roles(user) -> bool:
    """Role administration remains restricted to the system superuser."""
    return bool(getattr(user, "is_authenticated", False) and getattr(user, "is_superuser", False))


def impersonation_target_kind(user) -> str:
    """Return the permitted OPAL impersonation target kind, if any.

    Existing policy is preserved: only active teacher or parent accounts that are
    neither staff nor superusers can be impersonated.
    """
    if not getattr(user, "is_active", False):
        return ""
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return ""

    Teacher = apps.get_model("teachers", "Teacher")
    if Teacher.objects.filter(user=user, is_active=True).exists():
        return "teacher"

    Family = apps.get_model("parent_portal", "Family")
    if Family.objects.filter(user=user, is_active=True).exists():
        return "parent"
    return ""


def role_list_queryset():
    """Return roles using the model's current canonical ordering."""
    Role = apps.get_model("accounts", "Role")
    return Role.objects.all()
