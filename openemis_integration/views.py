from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from students.models import Student
from .forms import OpenEMISSettingsForm
from .models import OpenEMISSyncLog
from .services import active_school, get_openemis_settings, test_openemis_connection, queue_student_push, mark_student_synced


def can_manage_openemis(user):
    return user.is_superuser or user.is_staff


@login_required
@user_passes_test(can_manage_openemis)
def settings_view(request):
    school = active_school()
    settings = get_openemis_settings(school)
    if request.method == "POST":
        form = OpenEMISSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, "تم حفظ إعدادات OpenEMIS بنجاح.")
            return redirect("openemis:settings")
    else:
        form = OpenEMISSettingsForm(instance=settings)
    logs = OpenEMISSyncLog.objects.select_related("student", "created_by")[:20]
    return render(request, "openemis/settings.html", {"form": form, "logs": logs, "settings": settings})


@login_required
@user_passes_test(can_manage_openemis)
def test_connection_view(request):
    log = test_openemis_connection(request.user)
    if log.status == "success":
        messages.success(request, log.message)
    elif log.status == "failed":
        messages.error(request, log.message)
    else:
        messages.warning(request, log.message)
    return redirect("openemis:settings")


@login_required
@user_passes_test(can_manage_openemis)
def logs_view(request):
    logs = OpenEMISSyncLog.objects.select_related("student", "created_by")[:200]
    return render(request, "openemis/logs.html", {"logs": logs})


@login_required
@user_passes_test(can_manage_openemis)
def student_push_view(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    log = queue_student_push(student, request.user, reason="manual")
    messages.success(request, f"تم إنشاء عملية مزامنة للطالب: {student.full_name} - الحالة: {log.get_status_display()}")
    return redirect("students:student_detail", pk=student.pk)


@login_required
@user_passes_test(can_manage_openemis)
def mark_synced_view(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    ministry_id = request.POST.get("ministry_student_id") or student.ministry_student_id
    mark_student_synced(student, ministry_id, request.user, response={"manual": True})
    messages.success(request, "تم تحديث حالة مزامنة الطالب مع OpenEMIS داخل OPAL.")
    return redirect("students:student_detail", pk=student.pk)
