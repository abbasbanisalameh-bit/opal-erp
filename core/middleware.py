from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


class DevelopmentCenterAccessMiddleware:
    """Keep the separated development tool private to staff accounts."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/development/"):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not (request.user.is_staff or request.user.is_superuser):
                raise PermissionDenied("مركز التطوير مخصص لفريق التطوير المخول فقط.")
        return self.get_response(request)
