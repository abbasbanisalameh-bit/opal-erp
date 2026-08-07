from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


class DevelopmentCenterAccessMiddleware:
    """Keep the development tool private to active system administrators."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/development/"):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not (request.user.is_active and request.user.is_superuser):
                raise PermissionDenied("مركز التطوير مخصص لمدير النظام الأعلى فقط.")
        return self.get_response(request)
