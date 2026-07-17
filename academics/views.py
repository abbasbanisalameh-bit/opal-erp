from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


@staff_member_required
def academics_dashboard(request):
    """Landing page for all academic sub-modules."""
    return render(request, "academics/dashboard.html")


@login_required
def student_list(request):
    """Compatibility redirect to the canonical students module."""
    return redirect("students:student_list")


@login_required
def student_create(request):
    """All new registrations go through the approved smart registration workflow."""
    return redirect("admissions:direct_registration")


@login_required
def student_detail(request, student_id):
    return redirect("students:student_360", pk=student_id)


@login_required
def student_update(request, student_id):
    return redirect("students:student_update", pk=student_id)


@login_required
def student_admission(request):
    return redirect("admissions:direct_registration")


@login_required
def student_academic_profile(request, pk):
    """Legacy academic profile URL; Student 360 is the only student profile."""
    return redirect("students:student_360", pk=pk)
