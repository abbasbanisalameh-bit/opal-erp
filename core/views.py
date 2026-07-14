from django.shortcuts import render

# Create your views here.

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from .models import Branch, School
from .forms import BranchForm, SchoolSettingsForm

def can_manage_system(user):
    return user.is_superuser or user.is_staff

@login_required
@user_passes_test(can_manage_system)
def system_settings(request):
    school = School.objects.filter(is_active=True).first() or School.objects.create(name="OPAL School")
    if request.method == "POST":
        action = request.POST.get("action", "settings")
        if action in {"seed_demo", "reset_demo"}:
            if not request.user.is_superuser:
                messages.error(request, "إدارة البيانات التجريبية متاحة لمدير النظام الأعلى فقط.")
                return redirect("core:system_settings")
            from .demo_data import reset_demo_school, seed_demo_school
            if action == "seed_demo":
                result = seed_demo_school(student_count=100, teacher_count=20, user=request.user)
                messages.success(request, f"تم تجهيز {result['students']} طالب و{result['teachers']} معلم و{result['families']} أسرة تجريبية.")
            elif request.POST.get("confirmation") == "RESET-DEMO":
                result = reset_demo_school()
                messages.success(request, f"تم حذف التجريبي فقط: {result['students']} طالب و{result['teachers']} معلم.")
            else:
                messages.error(request, "تعذر التصفير: تأكيد العملية غير صحيح.")
            return redirect("core:system_settings")
        form = SchoolSettingsForm(request.POST, request.FILES, instance=school)
        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث إعدادات النظام بنجاح.")
            return redirect("core:system_settings")
    else:
        form = SchoolSettingsForm(instance=school)
    return render(request, "core/system_settings.html", {"form": form, "school": school})


@login_required
@user_passes_test(can_manage_system)
def branch_list(request):
    school = School.objects.filter(is_active=True).first() or School.objects.first()
    if school is None:
        messages.error(request, "أدخل بيانات المدرسة أولًا.")
        return redirect("core:system_settings")
    form = BranchForm(request.POST or None, school=school)
    if request.method == "POST" and form.is_valid():
        branch = form.save(commit=False)
        branch.school = school
        if branch.is_main:
            Branch.objects.filter(school=school).update(is_main=False)
        branch.save()
        messages.success(request, "تم حفظ الفرع من واجهة النظام.")
        return redirect("core:branch_list")
    return render(request, "core/branch_list.html", {"school": school, "form": form, "branches": school.branches.all()})


@login_required
@user_passes_test(can_manage_system)
def branch_update(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    form = BranchForm(request.POST or None, instance=branch, school=branch.school)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        if item.is_main:
            Branch.objects.filter(school=branch.school).exclude(pk=branch.pk).update(is_main=False)
        item.save()
        messages.success(request, "تم تعديل الفرع.")
        return redirect("core:branch_list")
    return render(request, "core/branch_form.html", {"form": form, "title": "تعديل الفرع"})


def admin_disabled(request):
    from django.http import HttpResponseNotFound
    return HttpResponseNotFound("لوحة Django Admin غير مستخدمة في OPAL ERP. أدخل البيانات من واجهة النظام.")


@login_required
@user_passes_test(lambda user: user.is_superuser)
def integrity_center(request):
    from .data_integrity import run_integrity_audit
    from .models import DataIntegrityRun

    if request.method == "POST":
        action = request.POST.get("action")
        if action in {"scan", "fix_safe"}:
            run = run_integrity_audit(fix_safe=(action == "fix_safe"), user=request.user)
            if action == "fix_safe":
                messages.success(request, f"اكتمل الإصلاح الآمن: عولجت {run.fixed_count} مشكلة، وبقيت {run.critical_count} حرجة للمراجعة.")
            else:
                messages.success(request, f"اكتمل الفحص: {run.total_issues} مشكلة، منها {run.critical_count} حرجة.")
            return redirect(f"{request.path}?run={run.pk}")

    runs = DataIntegrityRun.objects.select_related("created_by")[:20]
    run_id = request.GET.get("run")
    selected_run = DataIntegrityRun.objects.filter(pk=run_id).first() if run_id else runs.first()
    issues = selected_run.issues.all() if selected_run else []
    severity = request.GET.get("severity", "")
    if severity and selected_run:
        issues = issues.filter(severity=severity)
    return render(request, "core/integrity_center.html", {
        "runs": runs, "selected_run": selected_run, "issues": issues,
        "selected_severity": severity,
    })
