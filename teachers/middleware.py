from django.shortcuts import redirect

from .permissions import is_teacher_user


class TeacherPortalAccessMiddleware:
    """Restrict active teacher accounts to their portal and session endpoints."""

    ALLOWED_PREFIXES = (
        "/teachers/portal/",
        "/accounts/",
        "/logout/",
        "/static/",
        "/media/",
        "/enterprise/workflow/",
        "/enterprise/notifications/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_teacher_user(request.user) and not (request.user.is_staff or request.user.is_superuser):
            if request.path == "/":
                return redirect("teachers:portal_dashboard")
            if not request.path.startswith(self.ALLOWED_PREFIXES):
                return redirect("teachers:portal_dashboard")
        return self.get_response(request)
