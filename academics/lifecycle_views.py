from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from enterprise_ops.services import audit, notify_management
from students.models import Student
from enterprise_ops.permissions import management_required

from .lifecycle import perform_lifecycle_action
from .lifecycle_forms import BulkPromotionForm, StudentLifecycleForm
from .models import Enrollment, StudentLifecycleEvent


@management_required
def lifecycle_list(request):
    events = StudentLifecycleEvent.objects.select_related(
        "student", "from_enrollment__grade", "to_enrollment__grade", "performed_by"
    )
    action = request.GET.get("action", "")
    if action:
        events = events.filter(action=action)
    return render(
        request,
        "academics/lifecycle/list.html",
        {"events": events[:500], "actions": StudentLifecycleEvent.ACTION_CHOICES, "selected_action": action},
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
            form.add_error(None, exc.message)
        else:
            audit(request, "update", "academics.StudentLifecycleEvent", event.pk, f"{event.get_action_display()} للطالب {student.full_name}")
            notify_management("حركة طالب", f"{event.get_action_display()} - {student.full_name}", "info", f"/students/{student.pk}/360/", exclude_user=request.user)
            messages.success(request, "تم تنفيذ حركة الطالب وتسجيلها في السجل.")
            return redirect("academics:lifecycle_list")
    return render(request, "academics/lifecycle/action.html", {"student": student, "form": form, "current": current})


@management_required
def promotion_batch(request):
    form = BulkPromotionForm(
        request.POST or None,
        initial={
            "effective_date": timezone.localdate(),
            "source_year": request.GET.get("source_year") or None,
        },
    )
    enrollments = Enrollment.objects.none()
    selected_operation = request.POST.get("operation", "promote")
    if request.method == "POST" and request.POST.get("load"):
        if form.is_valid():
            enrollments = Enrollment.objects.filter(
                academic_year=form.cleaned_data["source_year"],
                grade=form.cleaned_data["source_grade"],
                status="active",
            ).select_related("student", "section")
    elif request.method == "POST" and (request.POST.get("execute") or request.POST.get("promote")):
        if form.is_valid():
            selected_operation = form.cleaned_data["operation"]
            ids = request.POST.getlist("students")
            enrollments = Enrollment.objects.filter(
                pk__in=ids,
                academic_year=form.cleaned_data["source_year"],
                grade=form.cleaned_data["source_grade"],
                status="active",
            ).select_related("student")
            completed = 0
            failures = []
            with transaction.atomic():
                for enrollment in enrollments:
                    try:
                        perform_lifecycle_action(
                            student=enrollment.student,
                            action=selected_operation,
                            effective_date=form.cleaned_data["effective_date"],
                            target_year=form.cleaned_data["target_year"],
                            target_grade=form.cleaned_data["target_grade"],
                            target_section=form.cleaned_data["target_section"],
                            reason=form.cleaned_data["reason"],
                            user=request.user,
                        )
                        completed += 1
                    except ValidationError as exc:
                        failures.append(f"{enrollment.student.full_name}: {exc.message}")
            if completed:
                action_label = "تخريج" if selected_operation == "graduate" else "ترفيع"
                audit(request, "update", "academics.Enrollment", description=f"{action_label} جماعي لعدد {completed} طالب")
                messages.success(request, f"تم {action_label} {completed} طالب بنجاح.")
            for failure in failures:
                messages.error(request, failure)
            if not failures:
                return redirect("academics:lifecycle_list")
    return render(
        request,
        "academics/lifecycle/promotion_batch.html",
        {"form": form, "enrollments": enrollments, "selected_operation": selected_operation},
    )
