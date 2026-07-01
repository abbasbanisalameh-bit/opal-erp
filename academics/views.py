from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from core.models import School, Branch
from core.services.sequences import generate_code
from .models import StudentRecord
from .forms import StudentRecordForm


@login_required
def student_list(request):
    students = StudentRecord.objects.all().order_by("full_name")

    return render(request, "academics/student_list.html", {
        "students": students,
        "total_students": students.count(),
        "active_students": students.filter(is_active=True).count(),
    })


@login_required
def student_create(request):
    if request.method == "POST":
        form = StudentRecordForm(request.POST, request.FILES)

        if form.is_valid():
            student = form.save(commit=False)
            student.school = School.objects.first()
            student.branch = Branch.objects.first()
            student.student_number = generate_code("student", "STD")
            student.save()
            return redirect("academics:student_list")
    else:
        form = StudentRecordForm()

    return render(request, "academics/student_form.html", {
        "form": form,
        "title": "إضافة طالب جديد",
    })


@login_required
def student_detail(request, student_id):
    student = StudentRecord.objects.get(id=student_id)

    return render(request, "academics/student_detail.html", {
        "student": student,
    })


@login_required
def student_update(request, student_id):
    student = StudentRecord.objects.get(id=student_id)

    if request.method == "POST":
        form = StudentRecordForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            form.save()
            return redirect("academics:student_detail", student_id=student.id)
    else:
        form = StudentRecordForm(instance=student)

    return render(request, "academics/student_form.html", {
        "form": form,
        "title": "تعديل بيانات الطالب",
    })


from .models import Guardian, StudentGuardian, Enrollment, AcademicYear
from .forms import StudentAdmissionForm


@login_required
def student_admission(request):
    if request.method == "POST":
        form = StudentAdmissionForm(request.POST, request.FILES)

        if form.is_valid():
            school = School.objects.first()
            branch = Branch.objects.first()
            academic_year = AcademicYear.objects.filter(is_current=True).first()

            student = StudentRecord.objects.create(
                school=school,
                branch=branch,
                student_number=generate_code("student", "STD"),
                full_name=form.cleaned_data["full_name"],
                father_name=form.cleaned_data["father_name"],
                mother_name=form.cleaned_data["mother_name"],
                gender=form.cleaned_data["gender"],
                phone=form.cleaned_data["phone"],
                address=form.cleaned_data["address"],
                photo=form.cleaned_data.get("photo"),
                is_active=True,
            )

            guardian = Guardian.objects.create(
                school=school,
                full_name=form.cleaned_data["guardian_name"],
                relation=form.cleaned_data["guardian_relation"],
                phone=form.cleaned_data["guardian_phone"],
                email=form.cleaned_data["guardian_email"],
                job_title=form.cleaned_data["guardian_job"],
                is_active=True,
            )

            StudentGuardian.objects.create(
                student=student,
                guardian=guardian,
                is_primary=True,
                can_receive_notifications=True,
                can_pickup_student=True,
            )

            if academic_year:
                Enrollment.objects.create(
                    student=student,
                    academic_year=academic_year,
                    grade=form.cleaned_data["grade"],
                    section=form.cleaned_data["section"],
                    status="active",
                )

            return redirect("academics:student_detail", student_id=student.id)

    else:
        form = StudentAdmissionForm()

    return render(request, "academics/student_admission.html", {
        "form": form,
        "title": "تسجيل طالب جديد",
    })

from django.shortcuts import render, get_object_or_404
from .models import StudentRecord


def student_academic_profile(request, pk):
    student = get_object_or_404(StudentRecord, pk=pk)

    enrollments = student.enrollments.select_related(
        "academic_year", "grade", "section"
    ).all()

    guardians = student.guardians.select_related("guardian").all()
    documents = student.documents.all()

    current_enrollment = enrollments.first()

    return render(request, "academics/students/academic_profile.html", {
        "student": student,
        "current_enrollment": current_enrollment,
        "enrollments": enrollments,
        "guardians": guardians,
        "documents": documents,
    })
