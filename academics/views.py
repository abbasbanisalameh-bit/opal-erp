from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from core.models import School, Branch
from core.services.sequences import generate_code
from students.models import Student
from students.forms import StudentForm


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
    return redirect("students:student_detail", pk=student_id)


@login_required
def student_update(request, student_id):
    return redirect("students:student_update", pk=student_id)


@login_required
def student_admission(request):
    return redirect("admissions:direct_registration")


from django.shortcuts import render, get_object_or_404
from students.models import Student


def student_academic_profile(request, pk):
    student = get_object_or_404(Student, pk=pk)

    enrollments = student.enrollments.select_related(
        "academic_year", "grade", "section"
    ).all()

    guardians = student.family_links.filter(is_active=True).select_related("family").all()
    documents = student.documents.all()

    current_enrollment = enrollments.first()

    return render(request, "academics/students/academic_profile.html", {
        "student": student,
        "current_enrollment": current_enrollment,
        "enrollments": enrollments,
        "guardians": guardians,
        "documents": documents,
    })
