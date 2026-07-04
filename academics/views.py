from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from core.models import School, Branch
from core.services.sequences import generate_code
from students.models import Student
from students.forms import StudentForm


@login_required
def student_list(request):
    students = Student.objects.all().order_by("full_name")

    return render(request, "academics/student_list.html", {
        "students": students,
        "total_students": students.count(),
        "active_students": students.filter(is_active=True).count(),
    })


@login_required
def student_create(request):
    if request.method == "POST":
        form = StudentForm(request.POST, request.FILES)

        if form.is_valid():
            student = form.save(commit=False)
            student.school = School.objects.first()
            student.branch = Branch.objects.first()
            student.student_number = generate_code("student", "STD")
            student.save()
            return redirect("academics:student_list")
    else:
        form = StudentForm()

    return render(request, "academics/student_form.html", {
        "form": form,
        "title": "إضافة طالب جديد",
    })


@login_required
def student_detail(request, student_id):
    student = Student.objects.get(id=student_id)

    return render(request, "academics/student_detail.html", {
        "student": student,
    })


@login_required
def student_update(request, student_id):
    student = Student.objects.get(id=student_id)

    if request.method == "POST":
        form = StudentForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            form.save()
            return redirect("academics:student_detail", student_id=student.id)
    else:
        form = StudentForm(instance=student)

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

            AcademicYearModel = Enrollment._meta.get_field("academic_year").remote_field.model
            academic_year = AcademicYearModel.objects.order_by("-start_date").first()

            student = Student.objects.create(
                school=school,
                branch=branch,
                student_number=generate_code("student", "STD"),
                full_name=form.cleaned_data.get("full_name", ""),
                father_name=form.cleaned_data.get("father_name", ""),
                mother_name="",
                gender=form.cleaned_data.get("gender", ""),
                phone=form.cleaned_data.get("phone", ""),
                address=form.cleaned_data.get("address", ""),
                photo=form.cleaned_data.get("photo"),
                is_active=True,
            )

            guardian = Guardian.objects.create(
                school=school,
                full_name=form.cleaned_data.get("guardian_name", ""),
                relation=form.cleaned_data.get("guardian_relation", "father"),
                phone=form.cleaned_data.get("guardian_phone", ""),
                email=form.cleaned_data.get("guardian_email", ""),
                job_title=form.cleaned_data.get("guardian_job", ""),
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
                    grade=form.cleaned_data.get("grade"),
                    section=form.cleaned_data.get("section"),
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
from students.models import Student


def student_academic_profile(request, pk):
    student = get_object_or_404(Student, pk=pk)

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
