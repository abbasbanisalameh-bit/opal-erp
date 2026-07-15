from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.forms import modelform_factory
from django.shortcuts import get_object_or_404, redirect, render

from core.models import AcademicYear, School, Semester

from .forms import AcademicStructureGradeForm, AcademicStructureSectionForm, AcademicStructureYearForm, GradeForm, SectionForm
from .models import Grade, Section, Subject


AcademicYearForm = modelform_factory(
    AcademicYear,
    fields=["school", "name", "start_date", "midyear_break_start", "midyear_break_end", "end_date", "is_current"],
)
SubjectForm = modelform_factory(
    Subject,
    fields=["name", "code", "grade", "is_active"],
)

def _style_form(form):
    for field in form.fields.values():
        css = "form-check-input" if getattr(field.widget, "input_type", "") == "checkbox" else "form-control"
        field.widget.attrs.setdefault("class", css)
    return form


def _school_for_academics():
    """Use the existing active school and never create a parallel academic structure."""
    return School.objects.filter(is_active=True).first() or School.objects.first()


def _main_branch(school):
    branch = school.branches.filter(is_active=True, is_main=True).first()
    if branch is None:
        branch = school.branches.filter(is_active=True).first()
    if branch is None:
        branch, _ = school.branches.get_or_create(
            name="الفرع الرئيسي",
            defaults={"is_main": True, "is_active": True},
        )
    return branch


def _section_names(count):
    if count == 1:
        return ["الشعبة العامة"]
    letters = ["أ", "ب", "ج", "د", "هـ", "و", "ز", "ح", "ط", "ي", "ك", "ل", "م", "ن", "س", "ع", "ف", "ص", "ق", "ر", "ش", "ت", "ث", "خ", "ذ", "ض", "ظ", "غ"]
    return [letters[index] if index < len(letters) else f"شعبة {index + 1}" for index in range(count)]


@login_required
def academic_year_list(request):
    years = AcademicYear.objects.select_related("school").order_by("-start_date")
    return render(request, "academics/academic_year_list.html", {"years": years})


@login_required
def academic_year_create(request):
    messages.info(request, "إضافة العام الدراسي تتم من شاشة الهيكل الدراسي الموحدة.")
    return redirect("academics:academic_structure")


@login_required
def academic_year_update(request, pk):
    year = get_object_or_404(AcademicYear, pk=pk)
    form = _style_form(AcademicYearForm(request.POST or None, instance=year))
    if form.is_valid():
        year = form.save()
        if year.is_current:
            AcademicYear.objects.filter(school=year.school).exclude(pk=year.pk).update(is_current=False)
        return redirect("academics:academic_year_list")
    return render(request, "academics/academic_year_form.html", {"form": form, "title": "تعديل عام دراسي"})


@login_required
def academic_structure(request):
    """One operational screen for a year, its grades, fees, sections and homeroom teachers."""
    school = _school_for_academics()
    if school is None:
        messages.error(request, "أضف بيانات المدرسة أولًا من إعدادات النظام.")
        return redirect("core:system_settings")

    years = AcademicYear.objects.filter(school=school).order_by("-is_current", "-start_date")
    year_id = request.GET.get("year") or request.POST.get("academic_year")
    academic_year = years.filter(pk=year_id).first() if year_id else years.filter(is_current=True).first()
    academic_year = academic_year or years.first()
    year_form = AcademicStructureYearForm(request.POST or None, school=school, prefix="year")
    form = AcademicStructureGradeForm(request.POST or None, school=school, prefix="grade")
    section_form = AcademicStructureSectionForm(request.POST or None, school=school, academic_year=academic_year, prefix="section")

    if request.method == "POST" and request.POST.get("action") == "create_year" and year_form.is_valid():
        year = year_form.save(commit=False)
        year.school = school
        year.save()
        messages.success(request, "تمت إضافة العام الدراسي. أضف الآن صفوفه من الشاشة نفسها.")
        return redirect(f"{request.path}?year={year.pk}")

    if academic_year and request.method == "POST" and request.POST.get("action") == "configure_grade" and form.is_valid():
        with transaction.atomic():
            grade, created = Grade.objects.get_or_create(
                school=school,
                name=form.cleaned_data["name"],
                defaults={
                    "order": form.cleaned_data["order"],
                    "is_kindergarten": form.cleaned_data["is_kindergarten"],
                    "is_active": True,
                },
            )
            if not created:
                grade.order = form.cleaned_data["order"]
                grade.is_kindergarten = form.cleaned_data["is_kindergarten"]
                grade.is_active = True
                grade.save(update_fields=["order", "is_kindergarten", "is_active"])

            from admissions.models import GradeFee

            fee = (
                GradeFee.objects.filter(school=school, academic_year=academic_year, grade=grade)
                .order_by("-updated_at", "-pk")
                .first()
            )
            if fee is None:
                GradeFee.objects.create(
                    school=school,
                    academic_year=academic_year,
                    grade=grade,
                    tuition_fee=form.cleaned_data["tuition_fee"],
                    is_active=True,
                )
            else:
                fee.tuition_fee = form.cleaned_data["tuition_fee"]
                fee.is_active = True
                fee.save(update_fields=["tuition_fee", "is_active", "updated_at"])

            branch = _main_branch(school)
            existing_sections = Section.objects.filter(
                academic_year=academic_year, branch=branch, grade=grade
            ).count()
            if not existing_sections:
                names = _section_names(form.cleaned_data["section_count"])
                teacher = form.cleaned_data["homeroom_teacher"] if len(names) == 1 else None
                for index, name in enumerate(names):
                    Section.objects.create(
                        academic_year=academic_year,
                        branch=branch,
                        grade=grade,
                        name=name,
                        homeroom_teacher=teacher if index == 0 else None,
                        is_default=(len(names) == 1),
                        is_active=True,
                    )
                detail = "تمت إضافة الصف ورسومه وشعبه."
            else:
                detail = "تم تحديث رسوم الصف. الشعب الموجودة لم تتغير حفاظًا على بياناتها."
        messages.success(request, detail)
        return redirect(f"{request.path}?year={academic_year.pk}")

    if academic_year and request.method == "POST" and request.POST.get("action") == "add_section" and section_form.is_valid():
        branch = _main_branch(school)
        grade = section_form.cleaned_data["grade"]
        name = section_form.cleaned_data["name"]
        if Section.objects.filter(academic_year=academic_year, branch=branch, grade=grade, name__iexact=name).exists():
            section_form.add_error("name", "هذه الشعبة موجودة مسبقًا لهذا الصف في العام الحالي.")
        else:
            Section.objects.create(
                academic_year=academic_year,
                branch=branch,
                grade=grade,
                name=name,
                capacity=section_form.cleaned_data["capacity"] or 0,
                homeroom_teacher=section_form.cleaned_data["homeroom_teacher"],
                is_active=True,
            )
            messages.success(request, "تمت إضافة الشعبة ومربي الصف من المدخل الموحد.")
            return redirect(f"{request.path}?year={academic_year.pk}")

    from admissions.models import GradeFee

    fees = {
        item.grade_id: item
        for item in GradeFee.objects.filter(school=school, academic_year=academic_year).order_by("-updated_at", "-pk")
    }
    grades = Grade.objects.filter(school=school, is_active=True).order_by("order", "name")
    sections = (
        Section.objects.filter(academic_year=academic_year, branch__school=school)
        .select_related("grade", "homeroom_teacher", "branch")
        .order_by("grade__order", "grade__name", "name")
    )
    sections_by_grade = {}
    for section in sections:
        sections_by_grade.setdefault(section.grade_id, []).append(section)
    structure_rows = [
        {"grade": grade, "fee": fees.get(grade.pk), "sections": sections_by_grade.get(grade.pk, [])}
        for grade in grades
        if grade.pk in fees or grade.pk in sections_by_grade
    ]
    return render(request, "academics/academic_structure.html", {
        "school": school,
        "years": years,
        "academic_year": academic_year,
        "year_form": year_form,
        "form": form,
        "section_form": section_form,
        "structure_rows": structure_rows,
    })


@login_required
def semester_list(request):
    semesters = Semester.objects.select_related("academic_year", "academic_year__school").order_by(
        "-academic_year__start_date", "start_date"
    )
    return render(request, "academics/semester_list.html", {"semesters": semesters})


@login_required
def semester_create(request):
    messages.info(request, "الفصلان الدراسيان يُنشآن تلقائيًا من العام الدراسي وعطلة منتصف العام.")
    return redirect("academics:academic_structure")


@login_required
def semester_update(request, pk):
    semester = get_object_or_404(Semester, pk=pk)
    messages.info(request, "تُعدل تواريخ الفصل من بيانات العام الدراسي وعطلة منتصف العام.")
    return redirect(f"/academics/structure/?year={semester.academic_year_id}")


@login_required
def semester_delete(request, pk):
    messages.error(request, "لا يمكن حذف أحد الفصلين الدراسيين؛ العام الدراسي مقسوم دائمًا إلى فصلين.")
    return redirect("academics:semester_list")


@login_required
def subject_list(request):
    subjects = Subject.objects.select_related("grade").order_by("grade__order", "name")
    return render(request, "academics/subject_list.html", {"subjects": subjects})


@login_required
def subject_create(request):
    form = _style_form(SubjectForm(request.POST or None))
    if form.is_valid():
        form.save()
        return redirect("academics:subject_list")
    return render(request, "academics/subject_form.html", {"form": form, "title": "إضافة مادة"})


@login_required
def subject_update(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    form = _style_form(SubjectForm(request.POST or None, instance=subject))
    if form.is_valid():
        form.save()
        return redirect("academics:subject_list")
    return render(request, "academics/subject_form.html", {"form": form, "title": "تعديل مادة"})


@login_required
def grade_list(request):
    school = _school_for_academics()
    grades = Grade.objects.select_related("school").filter(school=school) if school else Grade.objects.none()
    return render(request, "academics/grades/grade_list.html", {"grades": grades})


@login_required
def grade_create(request):
    messages.info(request, "إضافة الصف ورسومه وشعبه تتم من شاشة الهيكل الدراسي الموحدة.")
    return redirect("academics:academic_structure")


@login_required
def grade_update(request, pk):
    grade = get_object_or_404(Grade, pk=pk)
    form = GradeForm(request.POST or None, instance=grade, school=grade.school)
    if form.is_valid():
        form.save()
        return redirect("academics:grade_list")
    return render(request, "academics/grades/grade_form.html", {"form": form, "title": "تعديل صف دراسي"})


@login_required
def grade_delete(request, pk):
    grade = get_object_or_404(Grade, pk=pk)
    if request.method == "POST":
        has_dependencies = (
            grade.sections.exists()
            or grade.fee_settings.exists()
            or grade.subjects.exists()
            or grade.enrollment_set.exists()
        )
        if has_dependencies:
            messages.error(request, "لا يمكن حذف صف مرتبط برسوم أو شعب أو طلاب أو مواد. أوقفه بدلًا من الحذف.")
        else:
            grade.delete()
            messages.success(request, "تم حذف الصف غير المرتبط بأي بيانات.")
    return redirect("academics:grade_list")


@login_required
def section_list(request):
    school = _school_for_academics()
    sections = Section.objects.select_related("academic_year", "branch", "grade", "homeroom_teacher").filter(branch__school=school) if school else Section.objects.none()
    return render(request, "academics/sections/section_list.html", {"sections": sections})


@login_required
def section_create(request):
    messages.info(request, "إضافة الشعب تتم من شاشة الهيكل الدراسي الموحدة.")
    return redirect("academics:academic_structure")


@login_required
def section_update(request, pk):
    section = get_object_or_404(Section, pk=pk)
    form = SectionForm(request.POST or None, instance=section, school=section.branch.school, academic_year=section.academic_year)
    if form.is_valid():
        form.save()
        return redirect("academics:section_list")
    return render(request, "academics/sections/section_form.html", {"form": form, "title": "تعديل شعبة"})


@login_required
def section_delete(request, pk):
    section = get_object_or_404(Section, pk=pk)
    if request.method == "POST":
        if section.enrollments.exists():
            messages.error(request, "لا يمكن حذف شعبة مرتبطة بقيد طلاب. أوقفها بدلًا من الحذف.")
        else:
            section.delete()
            messages.success(request, "تم حذف الشعبة غير المرتبطة بأي طالب.")
    return redirect("academics:section_list")
