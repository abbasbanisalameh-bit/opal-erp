from django.conf import settings
from django.contrib.auth import get_user_model

from core.models import School


def opal_identity(request):
    school = None
    profile = None

    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        if profile and profile.school:
            school = profile.school

    if school is None:
        school = School.objects.filter(is_active=True).first()

    impersonator_id = request.session.get("opal_impersonator_user_id") if hasattr(request, "session") else None
    impersonator_name = request.session.get("opal_impersonator_username", "") if hasattr(request, "session") else ""
    if impersonator_id and not impersonator_name:
        User = get_user_model()
        impersonator_name = (
            User.objects.filter(pk=impersonator_id)
            .values_list("username", flat=True)
            .first()
            or "المدير العام"
        )

    return {
        "opal_school": school,
        "opal_profile": profile,
        "opal_openemis_enabled": settings.OPAL_ENABLE_OPENEMIS,
        "opal_development_center_enabled": settings.OPAL_ENABLE_DEVELOPMENT_CENTER,
        "opal_is_impersonating": bool(impersonator_id),
        "opal_impersonator_name": impersonator_name,
    }
