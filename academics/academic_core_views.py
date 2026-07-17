from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms import modelform_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.academic_years import academic_year_closure_report, activate_academic_year, close_academic_year
from core.models import AcademicYear, School, Semester
from enterprise_ops.permissions import management_required
from enterprise_ops.services import audit

from .forms import (
    AcademicStructureGradeForm,
    AcademicStructureSectionForm,
    AcademicStructureYearForm,
)
from .models import Grade, Section, Subject


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
    """Use the existing school and never create a parallel academic structure."""
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
    letters = [
        "أ", "ب", "ج", "د", "هـ", "و", "ز", "ح", "ط", "ي", "ك", "ل", "م", "ن",
        "س", "ع", "ف", "ص", "ق", "ر", "ش", "ت", "ث", "خ", "ذ", "ض", "ظ", "غ",
    ]
    return [letters[index] if index < len(letters) else f"شعبة {index + 1}" for index in range(count)]


def _structure_url(year_id=None, **params):
    url = reverse("academics:academic_structure")
    query = []
    if year_id:
        query.append(f"year={year_id}")
    query.extend(f"{key}={value}" for key, value in params.items() if value not in (None, ""))
    return f"{url}?{'&'.join(query)}" if query else url


@management_required
def academic_year_list(request):
    years = AcademicYear.objects.select_related("school").order_by("-start_date")
    return render(request, "academics/academic_year_list.html", {"years": years})


@management_required
def academic_year_create(request):
    school = _school_for_academics()
    if school is None:
        messages.error(request, "أضف بيانات المدرسة أولًا من إعدادات النظام.")
        return redirect("core:system_settings")
    form = AcademicStructureYearForm(request.POST or None, school=school)
    if form.is_valid():
        year = form.save(commit=False)
        year.school = school
        try:
            year.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            audit(request, "create", "core.AcademicYear", year.pk, f"إنشاء العام الدراسي {year.name}")
            messages.success(request, "تم إنشاء العام وفصليه الدراسيين. جهّز صفوفه وشعبه قبل تفعيله.")
            return redirect(_structure_url(year.pk))
    return render(request, "academics/academic_year_form.html", {"form": form, "title": "إضافة عام دراسي"})


@management_required
def academic_year_update(request, pk):
    year = get_object_or_404(AcademicYear, pk=pk)
    if year.is_closed:
        messages.error(request, "العام مغلق ولا يمكن تعديل بياناته التاريخية.")
        return redirect("academics:academic_year_list")
    form = AcademicStructureYearForm(request.POST or None, instance=year, school=year.school)
    if form.is_valid():
        year = form.save()
        if year.is_current:
            AcademicYear.objects.filter(school=year.school).exclude(pk=year.pk).update(is_current=False)
        audit(request, "update", "core.AcademicYear", year.pk, f"تعديل العام الدراسي {year.name}")
        messages.success(request, "تم تحديث بيانات العام الدراسي.")
        return redirect("academics:academic_year_list")
    return render(request, "academics/academic_year_form.html", {"form": form, "title": "تعديل عام دراسي"})


@management_required
def academic_structure(request):
    """The single operational entry screen for grades and sections."""
    from admissions.models import GradeFee

    school = _school_for_academics()
    if school is None:
        messages.error(request, "أضف بيانات المدرسة أولًا من إعدادات النظام.")
        return redirect("core:system_settings")

    years = AcademicYear.objects.filter(school=school).order_by("-is_current", "-start_date")
    year_id = request.GET.get("year") or request.POST.get("academic_year")
    academic_year = years.filter(pk=year_id).first() if year_id else years.filter(is_current=True).first()
    academic_year = academic_year or years.first()

    action = request.POST.get("action") if request.method == "POST" else ""
    if academic_year and academic_year.is_closed and action:
        messages.error(request, "العام مغلق؛ الهيكل الدراسي محفوظ للعرض ولا يقبل تعديلات جديدة.")
        return redirect(_structure_url(academic_year.pk))
    edit_grade_id = request.GET.get("edit_grade") or request.POST.get("grade-grade_id")
    edit_section_id = request.GET.get("edit_section") or request.POST.get("section-section_id")

    edit_grade = Grade.objects.filter(pk=edit_grade_id, school=school).first() if edit_grade_id else None
    edit_section = None
    if edit_section_id and academic_year:
        edit_section = Section.objects.filter(
            pk=edit_section_id,
            academic_year=academic_year,
            branch__school=school,
        ).select_related("grade", "homeroom_teacher").first()

    year_form = AcademicStructureYearForm(
        request.POST if action == "create_year" else None,
        school=school,
        prefix="year",
    )

    grade_initial = None
    if edit_grade and academic_year:
        fee = GradeFee.objects.filter(
            school=school,
            academic_year=academic_year,
            grade=edit_grade,
        ).order_by("-updated_at", "-pk").first()
        sections = list(
            Section.objects.filter(academic_year=academic_year, grade=edit_grade, branch__school=school)
            .select_related("homeroom_teacher")
            .order_by("name")
        )
        grade_initial = {
            "grade_id": edit_grade.pk,
            "name": edit_grade.name,
            "order": edit_grade.order,
            "is_kindergarten": edit_grade.is_kindergarten,
            "is_active": edit_grade.is_active,
            "tuition_fee": fee.tuition_fee if fee else 0,
            "section_count": max(len(sections), 1),
            "homeroom_teacher": sections[0].homeroom_teacher if len(sections) == 1 else None,
        }

    grade_form = AcademicStructureGradeForm(
        request.POST if action == "configure_grade" else None,
        school=school,
        grade=edit_grade,
        prefix="grade",
        initial=grade_initial,
    )

    section_initial = None
    if edit_section:
        section_initial = {
            "section_id": edit_section.pk,
            "grade": edit_section.grade,
            "name": edit_section.name,
            "capacity": edit_section.capacity,
            "homeroom_teacher": edit_section.homeroom_teacher,
            "is_default": edit_section.is_default,
            "is_active": edit_section.is_active,
        }

    section_form = AcademicStructureSectionForm(
        request.POST if action in {"add_section", "save_section"} else None,
        school=school,
        academic_year=academic_year,
        section=edit_section,
        prefix="section",
        initial=section_initial,
    )

    if action == "create_year" and year_form.is_valid():
        year = year_form.save(commit=False)
        year.school = school
        year.save()
        messages.success(request, "تمت إضافة العام الدراسي. أضف الآن صفوفه من الشاشة نفسها.")
        return redirect(_structure_url(year.pk))

    if academic_year and action == "configure_grade" and grade_form.is_valid():
        with transaction.atomic():
            grade_id = grade_form.cleaned_data.get("grade_id")
            existing_grade = getattr(grade_form, "existing_grade", None)
            if grade_id:
                grade = get_object_or_404(Grade, pk=grade_id, school=school)
                created = False
            elif existing_grade is not None:
                grade = existing_grade
                created = False
            else:
                grade = Grade(school=school)
                created = True

            grade.name = grade_form.cleaned_data["name"]
            grade.order = grade_form.cleaned_data["order"]
            grade.is_kindergarten = grade_form.cleaned_data["is_kindergarten"]
            grade.is_active = grade_form.cleaned_data["is_active"]
            grade.save()

            fee = GradeFee.objects.filter(
                school=school,
                academic_year=academic_year,
                grade=grade,
            ).order_by("-updated_at", "-pk").first()
            if fee is None:
                fee = GradeFee(
                    school=school,
                    academic_year=academic_year,
                    grade=grade,
                )
            fee.tuition_fee = grade_form.cleaned_data["tuition_fee"]
            fee.is_active = grade.is_active
            fee.save()

            branch = _main_branch(school)
            existing_sections = list(
                Section.objects.filter(
                    academic_year=academic_year,
                    branch=branch,
                    grade=grade,
                ).order_by("pk")
            )
            if created and not existing_sections:
                names = _section_names(grade_form.cleaned_data["section_count"])
                teacher = grade_form.cleaned_data["homeroom_teacher"] if len(names) == 1 else None
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
                detail = "تمت إضافة الصف ورسومه وشعبه من المدخل الموحد."
            else:
                if len(existing_sections) == 1 and grade_form.cleaned_data["homeroom_teacher"]:
                    section = existing_sections[0]
                    section.homeroom_teacher = grade_form.cleaned_data["homeroom_teacher"]
                    section.save(update_fields=["homeroom_teacher"])
                detail = "تم تحديث الصف ورسومه. لم تُحذف أو تُستبدل أي شعبة موجودة."

        messages.success(request, detail)
        return redirect(_structure_url(academic_year.pk))

    if academic_year and action in {"add_section", "save_section"} and section_form.is_valid():
        with transaction.atomic():
            section_id = section_form.cleaned_data.get("section_id")
            if section_id:
                section = get_object_or_404(
                    Section,
                    pk=section_id,
                    academic_year=academic_year,
                    branch__school=school,
                )
                created = False
            else:
                section = Section(
                    academic_year=academic_year,
                    branch=_main_branch(school),
                )
                created = True

            section.grade = section_form.cleaned_data["grade"]
            section.name = section_form.cleaned_data["name"]
            section.capacity = section_form.cleaned_data["capacity"] or 0
            section.homeroom_teacher = section_form.cleaned_data["homeroom_teacher"]
            section.is_default = section_form.cleaned_data["is_default"]
            section.is_active = section_form.cleaned_data["is_active"]

            if section.is_default:
                Section.objects.filter(
                    academic_year=academic_year,
                    branch=section.branch,
                    grade=section.grade,
                ).exclude(pk=section.pk).update(is_default=False)
            section.save()

        messages.success(request, "تمت إضافة الشعبة من المدخل الموحد." if created else "تم تحديث الشعبة من المدخل الموحد.")
        return redirect(_structure_url(academic_year.pk))

    fees = {}
    grades = Grade.objects.filter(school=school).order_by("order", "name")
    sections = Section.objects.none()
    if academic_year:
        fees = {
            item.grade_id: item
            for item in GradeFee.objects.filter(
                school=school,
                academic_year=academic_year,
            ).order_by("-updated_at", "-pk")
        }
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

    return render(
        request,
        "academics/academic_structure.html",
        {
            "school": school,
            "years": years,
            "academic_year": academic_year,
            "year_form": year_form,
            "form": grade_form,
            "section_form": section_form,
            "structure_rows": structure_rows,
            "edit_grade": edit_grade,
            "edit_section": edit_section,
            "year_is_closed": bool(academic_year and academic_year.is_closed),
        },
    )


@management_required
def semester_list(request):
    semesters = Semester.objects.select_related("academic_year", "academic_year__school").order_by(
        "-academic_year__start_date", "start_date"
    )
    return render(request, "academics/semester_list.html", {"semesters": semesters})


@management_required
def semester_create(request):
    messages.info(request, "الفصلان الدراسيان يُنشآن تلقائيًا من العام الدراسي وعطلة منتصف العام.")
    return redirect("academics:academic_structure")


@management_required
def semester_update(request, pk):
    semester = get_object_or_404(Semester, pk=pk)
    messages.info(request, "تُعدل تواريخ الفصل من بيانات العام الدراسي وعطلة منتصف العام.")
    return redirect(_structure_url(semester.academic_year_id))


@management_required
def semester_delete(request, pk):
    messages.error(request, "لا يمكن حذف أحد الفصلين الدراسيين؛ العام الدراسي مقسوم دائمًا إلى فصلين.")
    return redirect("academics:semester_list")


@management_required
def subject_list(request):
    subjects = Subject.objects.select_related("grade").order_by("grade__order", "name")
    return render(request, "academics/subject_list.html", {"subjects": subjects})


@management_required
def subject_create(request):
    form = _style_form(SubjectForm(request.POST or None))
    if form.is_valid():
        form.save()
        return redirect("academics:subject_list")
    return render(request, "academics/subject_form.html", {"form": form, "title": "إضافة مادة"})


@management_required
def subject_update(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    form = _style_form(SubjectForm(request.POST or None, instance=subject))
    if form.is_valid():
        form.save()
        return redirect("academics:subject_list")
    return render(request, "academics/subject_form.html", {"form": form, "title": "تعديل مادة"})


@management_required
def grade_list(request):
    messages.info(request, "الهيكل الدراسي هو نافذة الصفوف الوحيدة.")
    return redirect("academics:academic_structure")


@management_required
def grade_create(request):
    messages.info(request, "إضافة الصف ورسومه وشعبه تتم من شاشة الهيكل الدراسي الموحدة.")
    return redirect("academics:academic_structure")


@management_required
def grade_update(request, pk):
    grade = get_object_or_404(Grade, pk=pk)
    messages.info(request, "تم فتح الصف داخل نافذة الهيكل الدراسي المعتمدة.")
    year_id = grade.school.academic_years.filter(is_current=True, is_closed=False).values_list("pk", flat=True).first()
    return redirect(_structure_url(year_id, edit_grade=grade.pk))


@management_required
def grade_delete(request, pk):
    grade = get_object_or_404(Grade, pk=pk)
    if request.method == "POST":
        has_dependencies = (
            grade.sections.exists()
            or grade.fee_settings.exists()
            or grade.subjects.exists()
            or grade.enrollments.exists()
        )
        if has_dependencies:
            messages.error(request, "لا يمكن حذف صف مرتبط برسوم أو شعب أو طلاب أو مواد. أوقفه من الهيكل الدراسي بدلًا من الحذف.")
        else:
            grade.delete()
            messages.success(request, "تم حذف الصف غير المرتبط بأي بيانات.")
    return redirect("academics:academic_structure")


@management_required
def section_list(request):
    messages.info(request, "الهيكل الدراسي هو نافذة الشعب الوحيدة.")
    return redirect("academics:academic_structure")


@management_required
def section_create(request):
    messages.info(request, "إضافة الشعب تتم من شاشة الهيكل الدراسي الموحدة.")
    return redirect("academics:academic_structure")


@management_required
def section_update(request, pk):
    section = get_object_or_404(Section, pk=pk)
    if section.academic_year.is_closed:
        messages.error(request, "العام مغلق ولا يمكن تعديل شعبه.")
        return redirect(_structure_url(section.academic_year_id))
    messages.info(request, "تم فتح الشعبة داخل نافذة الهيكل الدراسي المعتمدة.")
    return redirect(_structure_url(section.academic_year_id, edit_section=section.pk))


@management_required
def section_delete(request, pk):
    section = get_object_or_404(Section, pk=pk)
    year_id = section.academic_year_id
    if request.method == "POST":
        if section.academic_year.is_closed:
            messages.error(request, "العام مغلق ولا يمكن حذف شعبه التاريخية.")
        elif section.enrollments.exists():
            messages.error(request, "لا يمكن حذف شعبة مرتبطة بقيد طلاب. أوقفها من الهيكل الدراسي بدلًا من الحذف.")
        else:
            section.delete()
            messages.success(request, "تم حذف الشعبة غير المرتبطة بأي طالب.")
    return redirect(_structure_url(year_id))


@management_required
def academic_year_close(request, pk):
    year = get_object_or_404(
        AcademicYear.objects.select_related("school", "closed_by"),
        pk=pk,
    )
    if year.is_closed:
        messages.info(request, "هذا العام مغلق بالفعل.")
        return redirect("academics:academic_year_list")

    report = academic_year_closure_report(year)
    if request.method == "POST":
        try:
            closed_year, summary = close_academic_year(
                year=year,
                user=request.user,
                notes=request.POST.get("closure_notes", ""),
            )
        except ValidationError as exc:
            for message in exc.messages:
                messages.error(request, message)
            report = academic_year_closure_report(year)
        else:
            audit(
                request,
                "update",
                "core.AcademicYear",
                closed_year.pk,
                f"إغلاق العام الدراسي {closed_year.name}: {summary}",
            )
            messages.success(request, "تم إغلاق العام وقفل سجلاته التشغيلية مع إبقاء التحصيل المالي متاحًا.")
            return redirect("academics:academic_year_list")

    return render(
        request,
        "academics/academic_year_close.html",
        {"year": year, "report": report},
    )


@management_required
@require_POST
def academic_year_activate(request, pk):
    year = get_object_or_404(AcademicYear, pk=pk)
    try:
        year = activate_academic_year(year=year)
    except ValidationError as exc:
        for message in exc.messages:
            messages.error(request, message)
    else:
        audit(request, "update", "core.AcademicYear", year.pk, f"تفعيل العام الدراسي {year.name}")
        messages.success(request, f"أصبح {year.name} هو العام الدراسي الحالي.")
    return redirect("academics:academic_year_list")
