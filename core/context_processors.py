from django.conf import settings

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

    return {
        "opal_school": school,
        "opal_profile": profile,
        "opal_openemis_enabled": settings.OPAL_ENABLE_OPENEMIS,
        "opal_development_center_enabled": settings.OPAL_ENABLE_DEVELOPMENT_CENTER,
    }
