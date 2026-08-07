import csv

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .workflow import (
    build_attendance_detail_context,
    build_dashboard_context,
    build_executive_export_rows,
    build_executive_snapshot,
    is_management_user,
)

# Backward-compatible internal aliases used by existing tests and integrations.
_is_management_user = is_management_user
_executive_snapshot = build_executive_snapshot


@login_required
@user_passes_test(_is_management_user)
@require_GET
def home(request):
    """Render the fixed canonical manager dashboard.

    Update 131.7 permanently retires per-user dashboard customization.  The
    historical profile field is intentionally left dormant for safe rollback
    compatibility, but no runtime path reads or writes it.
    """
    return render(request, "dashboard/home.html", build_dashboard_context(request))


@login_required
@user_passes_test(_is_management_user)
def attendance_detail(request):
    return render(request, "dashboard/attendance_detail.html", build_attendance_detail_context(request=request))


@login_required
@user_passes_test(_is_management_user)
def executive_export_csv(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="opal_executive_snapshot.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["المؤشر", "القيمة"])
    writer.writerows(build_executive_export_rows(request=request))
    return response
