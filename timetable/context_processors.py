from core.request_scope import request_school
from enterprise_ops.permissions import is_management

from .live_services import school_live_status, teacher_live_status


def live_schedule(request):
    """Provide only the compact topbar state on global page renders.

    The full management status calculates current entries, teacher availability,
    section states, and grade summaries.  It belongs on the timetable/dashboard
    screens that actually display those details, not in a context processor that
    runs on every page.  Management pages therefore use the lightweight school
    state here, while teacher pages retain their own scoped current-class state.
    """
    if not getattr(getattr(request, "user", None), "is_authenticated", False):
        return {}
    if is_management(request.user):
        school = request_school(request)
        status = school_live_status(school) if school else None
    else:
        teacher = getattr(request.user, "teacher_profile", None)
        status = teacher_live_status(teacher) if teacher else None
    return {"opal_live_schedule": status}
