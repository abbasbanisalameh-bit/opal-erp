from django.shortcuts import redirect
from django.urls import reverse

from .permissions import is_parent_user


class ParentPortalAccessMiddleware:
    """Confine parent accounts to the parent portal and account session endpoints.

    Staff and superusers are never restricted by this middleware.
    """

    ALLOWED_PREFIXES = (
        "/parent/",
        "/accounts/login/",
        "/accounts/logout/",
        "/logout/",
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_parent_user(request.user):
            path = request.path
            if path == "/":
                return redirect("parent_portal:dashboard")
            if not path.startswith(self.ALLOWED_PREFIXES):
                return redirect("parent_portal:dashboard")
        return self.get_response(request)
