from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from admissions.services import active_school
from enterprise_ops.permissions import management_required
from enterprise_ops.services import audit, notify_management

from .forms import (
    AdvanceDisbursementForm,
    AdvanceRequestForm,
    PayrollAdjustmentForm,
    PayrollPeriodForm,
    TeacherTerminationForm,
)
from .models import Teacher, TeacherAdvance, TeacherPayroll
from .payroll_services import (
    acknowledge_advance,
    disburse_advance,
    generate_payroll_period,
    normalize_period,
    send_payroll,
    terminate_teacher,
)
from .permissions import teacher_required


def _error_messages(request, exc):
    for message in getattr(exc, "messages", [str(exc)]):
        messages.error(request, message)


@management_required
def payroll_center(request):
    school = active_school()
    raw_period = request.POST.get("period") or request.GET.get("period") or timezone.localdate().strftime("%Y-%m")
    try:
        period = normalize_period(raw_period)
    except ValidationError:
        period = timezone.localdate().replace(day=1)
    period_form = PayrollPeriodForm(request.POST or None, initial={"period": period})
    if request.method == "POST" and request.POST.get("action") == "generate" and period_form.is_valid():
        summary = generate_payroll_period(school=school, period=period_form.cleaned_data["period"], user=request.user)
        audit(request, "create", "teachers.TeacherPayroll", description=f"توليد رواتب {period:%Y-%m}: {summary}")
        messages.success(request, f"تم تجهيز الرواتب: {summary['created']} جديد و{summary['updated']} محدث، مع حفظ {summary['preserved']} سجل مرسل دون تعديل.")
        return redirect(f"{request.path}?period={period:%Y-%m}")

    payrolls = TeacherPayroll.objects.filter(teacher__school=school, period=period).select_related("teacher").prefetch_related("advances")
    advances = TeacherAdvance.objects.filter(teacher__school=school, status__in=["requested", "disbursed", "acknowledged"]).select_related("teacher", "disbursed_by")
    return render(request, "teachers/payroll_center.html", {
        "period": period,
        "period_form": period_form,
        "payrolls": payrolls,
        "advances": advances,
        "disbursement_form": AdvanceDisbursementForm(),
    })


@management_required
def payroll_update(request, pk):
    payroll = get_object_or_404(TeacherPayroll.objects.select_related("teacher"), pk=pk)
    if payroll.status == "acknowledged":
        messages.error(request, "بطاقة الراتب مقرّ بها ولا تعدل؛ أنشئ تصحيحًا إداريًا موثقًا عند الحاجة.")
        return redirect("teachers:payroll_center")
    form = PayrollAdjustmentForm(request.POST or None, instance=payroll)
    if request.method == "POST" and form.is_valid():
        payroll = form.save(commit=False)
        payroll.status = "corrected" if payroll.status in {"objection", "sent"} else "ready"
        payroll.save()
        audit(request, "update", "teachers.TeacherPayroll", payroll.pk, "تحديث بطاقة راتب وإعادة حساب الصافي")
        messages.success(request, "تم تحديث البطاقة وإعادة حساب صافي الراتب.")
        return redirect(f"{reverse('teachers:payroll_center')}?period={payroll.period:%Y-%m}")
    return render(request, "teachers/payroll_form.html", {"form": form, "payroll": payroll})


@management_required
@require_POST
def payroll_send(request, pk):
    payroll = get_object_or_404(TeacherPayroll, pk=pk)
    try:
        payroll = send_payroll(payroll=payroll, user=request.user)
    except ValidationError as exc:
        _error_messages(request, exc)
    else:
        audit(request, "update", "teachers.TeacherPayroll", payroll.pk, f"إرسال راتب بصافي {payroll.net_salary}")
        messages.success(request, "تم دفع الراتب وإرسال البطاقة للمعلم.")
    return redirect(f"{reverse('teachers:payroll_center')}?period={payroll.period:%Y-%m}")


@management_required
@require_POST
def advance_disburse(request, pk):
    advance = get_object_or_404(TeacherAdvance, pk=pk)
    form = AdvanceDisbursementForm(request.POST)
    if form.is_valid():
        try:
            advance = disburse_advance(advance=advance, user=request.user, **form.cleaned_data)
        except ValidationError as exc:
            _error_messages(request, exc)
        else:
            audit(request, "update", "teachers.TeacherAdvance", advance.pk, f"صرف سلفة {advance.amount}")
            messages.success(request, "تم صرف السلفة وإرسال طلب الإقرار للمعلم.")
    else:
        messages.error(request, "حدد طريقة الصرف وراجع بيانات السلفة.")
    return redirect("teachers:payroll_center")


@management_required
@require_POST
def advance_reject(request, pk):
    advance = get_object_or_404(TeacherAdvance, pk=pk, status="requested")
    advance.status = "cancelled"
    advance.admin_note = request.POST.get("admin_note", "").strip()
    advance.save(update_fields=["status", "admin_note"])
    audit(request, "update", "teachers.TeacherAdvance", advance.pk, "رفض طلب سلفة")
    messages.success(request, "تم إلغاء الطلب قبل الصرف مع حفظ السجل.")
    return redirect("teachers:payroll_center")


@teacher_required
def portal_payroll(request):
    teacher = request.user.teacher_profile
    form = AdvanceRequestForm(request.POST or None)
    if request.method == "POST" and request.POST.get("action") == "request_advance" and form.is_valid():
        advance = form.save(commit=False)
        advance.teacher = teacher
        advance.save()
        target = f"{reverse('teachers:payroll_center')}?period={timezone.localdate():%Y-%m}#advance-{advance.pk}"
        transaction.on_commit(lambda: notify_management(
            "طلب سلفة جديد",
            f"قدّم المعلم {teacher.full_name} طلب سلفة بقيمة {advance.amount}.",
            "warning",
            target,
            event_key=f"advance-requested:{advance.pk}",
        ))
        messages.success(request, "تم إرسال طلب السلفة دون الحاجة إلى كتابة سبب.")
        return redirect("teachers:portal_payroll")
    payrolls = teacher.payroll_records.prefetch_related("advances").all()
    advances = teacher.salary_advances.all()
    return render(request, "teachers/portal_payroll.html", {
        "teacher": teacher, "form": form, "payrolls": payrolls, "advances": advances,
    })


@teacher_required
@require_POST
def portal_advance_acknowledge(request, pk):
    advance = get_object_or_404(TeacherAdvance, pk=pk, teacher=request.user.teacher_profile)
    try:
        acknowledge_advance(advance=advance, teacher=request.user.teacher_profile)
    except ValidationError as exc:
        _error_messages(request, exc)
    else:
        target = f"{reverse('teachers:payroll_center')}?period={timezone.localdate():%Y-%m}#advance-{advance.pk}"
        transaction.on_commit(lambda: notify_management(
            "إقرار استلام سلفة",
            f"أقرّ المعلم {advance.teacher.full_name} باستلام السلفة بقيمة {advance.amount}.",
            "success",
            target,
            event_key=f"advance-acknowledged:{advance.pk}",
        ))
        messages.success(request, "تم الإقرار باستلام السلفة وستخصم مرة واحدة من الراتب التالي.")
    return redirect("teachers:portal_payroll")


@teacher_required
@require_POST
def portal_payroll_action(request, pk):
    payroll = get_object_or_404(TeacherPayroll, pk=pk, teacher=request.user.teacher_profile)
    action = request.POST.get("action")
    with transaction.atomic():
        payroll = TeacherPayroll.objects.select_for_update().get(pk=payroll.pk)
        if payroll.status != "sent":
            messages.error(request, "هذه البطاقة ليست بانتظار الإقرار.")
        elif action == "acknowledge":
            payroll.status = "acknowledged"
            payroll.acknowledged_at = timezone.now()
            payroll.save(update_fields=["status", "acknowledged_at", "updated_at"])
            target = f"{reverse('teachers:payroll_center')}?period={payroll.period:%Y-%m}#payroll-{payroll.pk}"
            transaction.on_commit(lambda: notify_management(
                "إقرار استلام راتب",
                f"أقرّ المعلم {payroll.teacher.full_name} باستلام راتب {payroll.period:%Y-%m} بقيمة {payroll.net_salary}.",
                "success",
                target,
                event_key=f"payroll-acknowledged:{payroll.pk}",
            ))
            messages.success(request, "تم الإقرار ببطاقة الراتب.")
        elif action == "object":
            text = request.POST.get("objection_text", "").strip()
            if not text:
                messages.error(request, "اكتب سبب الاعتراض.")
            else:
                payroll.status = "objection"
                payroll.objection_text = text
                payroll.save(update_fields=["status", "objection_text", "updated_at"])
                target = f"{reverse('teachers:payroll_center')}?period={payroll.period:%Y-%m}#payroll-{payroll.pk}"
                transaction.on_commit(lambda: notify_management(
                    "اعتراض على بطاقة راتب",
                    f"سجّل المعلم {payroll.teacher.full_name} اعتراضًا على راتب {payroll.period:%Y-%m}.",
                    "warning",
                    target,
                    event_key=f"payroll-objection:{payroll.pk}",
                ))
                messages.success(request, "تم إرسال الاعتراض للإدارة.")
        else:
            messages.error(request, "الإجراء غير معروف.")
    return redirect("teachers:portal_payroll")


@teacher_required
def portal_payroll_statement(request):
    teacher = request.user.teacher_profile
    payrolls = teacher.payroll_records.filter(paid_at__isnull=False).prefetch_related("advances").order_by("-paid_at", "-period")
    return render(request, "teachers/portal_payroll_statement.html", {"teacher": teacher, "payrolls": payrolls})


@management_required
def teacher_terminate(request, pk):
    teacher = get_object_or_404(Teacher.objects.select_related("user", "school"), pk=pk)
    if teacher.end_date and not teacher.is_active:
        messages.info(request, "خدمة هذا المعلم منتهية مسبقًا، وكتاب إنهاء الخدمة محفوظ في ملفه.")
        return redirect("teachers:teacher_detail", pk=teacher.pk)

    form = TeacherTerminationForm(
        request.POST or None, teacher=teacher, initial={"end_date": timezone.localdate()}
    )
    if request.method == "POST" and form.is_valid():
        try:
            teacher, document, summary = terminate_teacher(
                teacher=teacher,
                end_date=form.cleaned_data["end_date"],
                reason=form.cleaned_data["end_reason"],
                user=request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            audit(request, "update", "teachers.Teacher", teacher.pk, f"إنهاء خدمة المعلم: {summary}")
            audit(
                request,
                "create",
                "documents.IssuedDocument",
                document.pk,
                f"إصدار كتاب إنهاء خدمة تلقائي للمعلم {teacher.full_name}",
            )
            messages.success(
                request,
                "تم إنهاء الخدمة وإيقاف الحساب والتكليفات التشغيلية وإصدار كتاب إنهاء الخدمة تلقائيًا.",
            )
            return redirect("documents:document_detail", document_id=document.pk)
    return render(request, "teachers/teacher_termination.html", {"teacher": teacher, "form": form})
