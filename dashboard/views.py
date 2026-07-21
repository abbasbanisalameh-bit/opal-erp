import csv

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.shortcuts import render

from .workflow import (
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
def home(request):
    return render(request, "dashboard/home.html", build_dashboard_context())


@login_required
@user_passes_test(_is_management_user)
def executive_export_csv(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="opal_executive_snapshot.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["المؤشر", "القيمة"])
    writer.writerows(build_executive_export_rows())
    return response
