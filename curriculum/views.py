"""One-release legacy redirects for the retired Curriculum CRUD routes.

LEGACY / DEPRECATED — remove this module and the URL include in OPAL Update
132.  No internal OPAL link may target these views.
"""

from django.shortcuts import redirect

from enterprise_ops.permissions import management_required


_DEPRECATION_HEADERS = {
    "Deprecation": "true",
    "Sunset": "OPAL Update 132.0",
    "Link": '</academics/subjects/>; rel="successor-version"',
}


def _legacy_redirect(route):
    response = redirect(route)
    for key, value in _DEPRECATION_HEADERS.items():
        response[key] = value
    return response


@management_required
def curriculum_list(request):
    return _legacy_redirect("academics:subject_list")


@management_required
def curriculum_create(request):
    return _legacy_redirect("academics:subject_create")


@management_required
def curriculum_update(request, pk):
    return _legacy_redirect("academics:subject_list")


@management_required
def curriculum_delete(request, pk):
    return _legacy_redirect("academics:subject_list")
