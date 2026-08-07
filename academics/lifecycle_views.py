from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from enterprise_ops.services import audit, notify_management
from students.models import Student
from enterprise_ops.permissions import management_required

from .lifecycle import perform_lifecycle_action
from .lifecycle_forms import StudentLifecycleForm
from .workflow import build_lifecycle_list_context
from .year_transition import (
    annual_transition_report,
    execute_annual_transition,
    next_year_preparation_report,
    prepare_next_year,
)


@management_required
def lifecycle_list(request):
    action = request.GET.get("action", "")
    return render(
        request,
        "academics/lifecycle/list.html",
        build_lifecycle_list_context(action),
    )


@management_required
def lifecycle_action(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    initial = {"effective_date": timezone.localdate()}
    current = student.enrollments.filter(status="active").order_by("-academic_year__start_date").first()
    if current:
        initial.update({"target_year": current.academic_year, "target_grade": current.grade, "target_section": current.section})
    form = StudentLifecycleForm(request.POST or None, initial=initial)
    if form.is_valid():
        try:
            event = perform_lifecycle_action(student=student, user=request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc.messages[0] if getattr(exc, "messages", None) else str(exc))
        else:
            audit(request, "update", "academics.StudentLifecycleEvent", event.pk, f"{event.get_action_display()} للطالب {student.full_name}")
            notify_management("حركة طالب", f"{event.get_action_display()} - {student.full_name}", "info", f"/students/{student.pk}/360/", exclude_user=request.user)
            messages.success(request, "تم تنفيذ حركة الطالب وتسجيلها في السجل.")
            return redirect("academics:lifecycle_list")
    return render(request, "academics/lifecycle/action.html", {"student": student, "form": form, "current": current})


@management_required
def promotion_batch(request):
    messages.info(request, "تم توحيد الترفيع والتخريج الجماعي في مركز دورة العام لضمان التنفيذ الذري والحفاظ على الشعبة.")
    return redirect("academics:annual_lifecycle_center")


@management_required
def annual_lifecycle_center(request):
    from core.models import AcademicYear, Semester
    from admissions.services import active_school
    from exams.lifecycle import close_semester, reopen_semester, semester_closure_report

    school = active_school()
    years = AcademicYear.objects.filter(school=school).prefetch_related("semesters").order_by("-start_date")
    source_id = request.POST.get("source_year") or request.GET.get("source_year")
    target_id = request.POST.get("target_year") or request.GET.get("target_year")
    source = years.filter(pk=source_id).first() if source_id else None
    if source is None:
        source = years.filter(is_closed=True, transition_completed_at__isnull=True).first()
    source = source or years.filter(is_current=True, is_closed=False).first() or years.first()
    target = years.filter(pk=target_id).first() if target_id else None
    if target is None and source:
        target = years.filter(
            preparation_source=source,
            prepared_at__isnull=False,
            is_closed=False,
        ).order_by("start_date").first()
    target = target or (
        years.filter(start_date__gt=source.start_date, is_closed=False).order_by("start_date").first()
        if source else None
    )

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "prepare":
                if not source or not target:
                    raise ValidationError("حدد العام المصدر والعام الجديد.")
                prepared, summary = prepare_next_year(source_year=source, target_year=target, user=request.user)
                audit(request, "update", "core.AcademicYear", prepared.pk, f"تهيئة العام {prepared.name}: {summary}")
                if summary["already_prepared"]:
                    messages.info(request, "العام الجديد مهيأ سابقًا؛ لم تُكرر أي سجلات ولم تُستبدل مراجعات الإدارة.")
                else:
                    messages.success(
                        request,
                        f"تمت التهيئة ذريًا: {summary['sections_created']} شعبة، "
                        f"{summary['assignments_copied']} تكليف، و{summary['timetable_entries_copied']} حصة؛ "
                        "دون نسخ الطلاب أو العلامات أو الحضور أو الفواتير.",
                    )
            elif action == "transition":
                if request.POST.get("confirmation", "").strip() != "تنفيذ الانتقال السنوي":
                    raise ValidationError("اكتب العبارة: تنفيذ الانتقال السنوي")
                if not source or not target:
                    raise ValidationError("حدد العام المصدر والعام الجديد.")
                transitioned, summary = execute_annual_transition(
                    source_year=source,
                    target_year=target,
                    user=request.user,
                )
                audit(request, "update", "core.AcademicYear", transitioned.pk, f"الانتقال السنوي: {summary}")
                messages.success(request, f"اكتمل الانتقال السنوي ذريًا: {summary['promotions']} ترفيع و{summary['graduations']} تخريج.")
                for warning in summary.get("capacity_warnings", []):
                    messages.warning(request, warning)
                    notify_management(
                        "تنبيه سعة صف بعد الانتقال السنوي",
                        warning,
                        "warning",
                        f"{request.path}?source_year={source.pk}&target_year={target.pk}",
                        exclude_user=request.user,
                    )
            elif action in {"close_semester", "reopen_semester"}:
                semester = get_object_or_404(Semester, pk=request.POST.get("semester"), academic_year__school=school)
                if action == "close_semester":
                    semester, summary = close_semester(
                        semester=semester,
                        user=request.user,
                        notes=request.POST.get("notes", ""),
                    )
                    messages.success(request, f"تم إغلاق {semester.get_code_display()} وحفظ {summary['results']} نتيجة مادة فصلية.")
                else:
                    semester = reopen_semester(
                        semester=semester,
                        user=request.user,
                        reason=request.POST.get("reason", ""),
                    )
                    messages.success(request, f"أعيد فتح {semester.get_code_display()} بسبب موثق.")
                audit(request, "update", "core.Semester", semester.pk, action)
            else:
                raise ValidationError("الإجراء المطلوب غير معروف.")
        except ValidationError as exc:
            for message in exc.messages:
                messages.error(request, message)
        else:
            return redirect(f"{request.path}?source_year={source.pk if source else ''}&target_year={target.pk if target else ''}")

    transition = None
    preparation = None
    if source and target:
        try:
            transition = annual_transition_report(source_year=source, target_year=target)
        except ValidationError as exc:
            transition = {"blockers": exc.messages, "warnings": [], "plan": [], "metrics": {"students": 0, "promotions": 0, "graduations": 0}}
        try:
            preparation = next_year_preparation_report(source_year=source, target_year=target)
        except ValidationError:
            preparation = None
    semester_rows = []
    if source:
        for semester in source.semesters.order_by("code"):
            semester_rows.append({"semester": semester, "report": None if semester.is_closed else semester_closure_report(semester)})
    return render(request, "academics/annual_lifecycle_center.html", {
        "school": school,
        "years": years,
        "source": source,
        "target": target,
        "semester_rows": semester_rows,
        "preparation": preparation,
        "transition": transition,
    })
