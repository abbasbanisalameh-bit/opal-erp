from core.models import School

from .live_services import management_live_status, teacher_live_status


def live_schedule(request):
    if not request.user.is_authenticated:
        return {}
    teacher = getattr(request.user, "teacher_profile", None)
    if teacher:
        status = teacher_live_status(teacher)
    elif request.user.is_staff or request.user.is_superuser:
        profile = getattr(request.user, "profile", None)
        school = getattr(profile, "school", None) or School.objects.filter(is_active=True).first()
        status = management_live_status(school) if school else None
    else:
        status = None
    return {"opal_live_schedule": status}
