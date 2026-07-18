from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from enterprise_ops.permissions import management_required
from enterprise_ops.models import WorkflowRequest
from enterprise_ops.services import audit, transition_workflow
from students.models import Student

from admissions.services import active_school

from .forms import (
    DiscountRequestForm, ExpenseEntryForm, FeeCategoryForm, FinancialYearClosureForm,
    InstallmentForm, MonthlyFinancialTargetForm, StudentInvoiceForm, StudentPaymentForm,
)
from .financial_services import (
    close_financial_year, collection_dashboard, monthly_financial_report,
    next_expense_number, normalize_period_end,
)
from .models import DiscountRequest, ExpenseEntry, FeeCategory, FinancialYearClosure, Installment, MonthlyFinancialTarget, Receipt, StudentInvoice, StudentPayment
from .services import create_discount_workflow, decide_discount
from .services.pdf import receipt_pdf
from .services.receipt import generate_receipt_number


@login_required
@management_required
def finance_dashboard(request):
    return render(request, "accounting/dashboard.html", collection_dashboard(active_school()))


@login_required
def retired_finance_screen(request, *args, **kwargs):
    messages.info(request, "تم توحيد هذه الوظيفة في شاشة تسديد الرسوم المعتمدة.")
    return redirect("admissions:fee_payment_create")


@login_required
def retired_receipts_screen(request, *args, **kwargs):
    messages.info(request, "تم توحيد الإيصالات في أرشيف تسديد الرسوم المعتمد.")
    return redirect("admissions:fee_payment_archive")


@login_required
@management_required
def fee_category_list(request):
    form = FeeCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        category = form.save()
        audit(request, "create", "accounting.FeeCategory", category.pk, f"إضافة فئة رسوم {category.name}")
        messages.success(request, "تمت إضافة فئة الرسوم من واجهة النظام.")
        return redirect("accounting:fee_category_list")
    return render(request, "accounting/fee_category_list.html", {"form": form, "items": FeeCategory.objects.all()})


@login_required
@management_required
def fee_category_update(request, pk):
    category = get_object_or_404(FeeCategory, pk=pk)
    form = FeeCategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit(request, "update", "accounting.FeeCategory", category.pk, f"تعديل فئة رسوم {category.name}")
        messages.success(request, "تم تعديل فئة الرسوم.")
        return redirect("accounting:fee_category_list")
    return render(request, "accounting/form.html", {"form": form, "title": "تعديل فئة رسوم"})


@login_required
@management_required
def invoice_list(request):
    invoices = StudentInvoice.objects.select_related("student", "fee_category", "academic_year").prefetch_related("payments")
    status = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()
    overdue = request.GET.get("overdue") == "1"
    if status:
        invoices = invoices.filter(status=status)
    if q:
        invoices = invoices.filter(Q(student__full_name__icontains=q) | Q(student__student_number__icontains=q) | Q(invoice_number__icontains=q))
    items = list(invoices[:1000])
    if overdue:
        items = [item for item in items if item.is_overdue]
    return render(request, "accounting/invoice_list.html", {"invoices": items, "statuses": StudentInvoice.STATUS_CHOICES, "filters": {"status": status, "q": q, "overdue": overdue}})


@login_required
@management_required
def invoice_create(request):
    form = StudentInvoiceForm(request.POST or None)
    if form.is_valid():
        invoice = form.save(commit=False)
        invoice.created_by = request.user
        invoice.full_clean()
        invoice.save()
        audit(request, "create", "accounting.StudentInvoice", invoice.pk, f"إصدار رسوم {invoice.invoice_number} للطالب {invoice.student.full_name}")
        messages.success(request, "تم إصدار الرسوم بنجاح.")
        return redirect("accounting:invoice_list")
    return render(request, "accounting/form.html", {"form": form, "title": "إصدار رسوم"})


@login_required
@management_required
def payment_create(request):
    form = StudentPaymentForm(request.POST or None)
    if form.is_valid():
        payment = form.save(commit=False)
        payment.created_by = request.user
        try:
            payment.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            receipt, _ = Receipt.objects.get_or_create(payment=payment, defaults={"receipt_number": generate_receipt_number()})
            audit(request, "create", "accounting.StudentPayment", payment.pk, f"دفعة {payment.amount} على {payment.invoice.invoice_number}")
            messages.success(request, f"تم تسجيل الدفعة وإصدار الإيصال {receipt.receipt_number}.")
            return redirect("accounting:receipt_list")
    return render(request, "accounting/form.html", {"form": form, "title": "تسجيل دفعة"})


@login_required
@management_required
@require_POST
def payment_reverse(request, payment_id):
    messages.info(request, "تصحيح الإيصالات يتم من الأرشيف بواسطة الحذف الآمن.")
    return redirect("admissions:fee_payment_archive")


@login_required
@management_required
@require_POST
def payment_safe_delete(request, payment_id):
    payment = get_object_or_404(StudentPayment.objects.select_related("invoice__academic_year", "invoice__student"), pk=payment_id)
    reason = request.POST.get("reason", "").strip()
    if payment.invoice.academic_year_id and FinancialYearClosure.objects.filter(source_year_id=payment.invoice.academic_year_id).exists():
        messages.error(request, "لا يمكن حذف إيصال داخل عام مغلق ماليًا.")
        return redirect("admissions:fee_payment_archive")
    try:
        changed = payment.safe_delete(request.user, reason)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        if changed:
            receipt_number = getattr(getattr(payment, "receipt", None), "receipt_number", payment.reference or payment.pk)
            audit(request, "delete", "accounting.StudentPayment", payment.pk, f"حذف آمن للإيصال {receipt_number}: {reason}")
            messages.success(request, "تم حذف الإيصال السابق بأمان وتحديث الرصيد.")
        else:
            messages.info(request, "الإيصال محذوف مسبقًا.")
    return redirect("admissions:fee_payment_archive")


@login_required
@management_required
def expense_list(request):
    school = active_school()
    form = ExpenseEntryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.school = school
        item.expense_number = next_expense_number()
        item.created_by = request.user
        item.save()
        audit(request, "create", "accounting.ExpenseEntry", item.pk, f"تسجيل مصروف {item.expense_number}: {item.amount}")
        messages.success(request, "تم تسجيل المصروف ضمن الكشف المالي المستقل.")
        return redirect("accounting:expense_list")
    items = ExpenseEntry.objects.filter(school=school, is_deleted=False).select_related("created_by")[:500]
    return render(request, "accounting/expense_list.html", {"form": form, "items": items})


@login_required
@management_required
@require_POST
def expense_safe_delete(request, pk):
    item = get_object_or_404(ExpenseEntry, pk=pk, school=active_school(), is_deleted=False)
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "اكتب سبب الحذف الآمن.")
    else:
        item.is_deleted = True
        item.deleted_by = request.user
        item.deleted_at = timezone.now()
        item.deletion_reason = reason
        item.save(update_fields=["is_deleted", "deleted_by", "deleted_at", "deletion_reason"])
        audit(request, "delete", "accounting.ExpenseEntry", item.pk, f"حذف آمن للمصروف {item.expense_number}: {reason}")
        messages.success(request, "تم حذف المصروف بأمان مع بقاء سجل التدقيق.")
    return redirect("accounting:expense_list")


@login_required
@management_required
def monthly_report(request):
    school = active_school()
    try:
        period_end = normalize_period_end(request.GET.get("period_end"))
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        period_end = normalize_period_end()
    target, _ = MonthlyFinancialTarget.objects.get_or_create(school=school, period_end=period_end)
    target_form = MonthlyFinancialTargetForm(request.POST or None, instance=target)
    if request.method == "POST" and target_form.is_valid():
        item = target_form.save(commit=False)
        item.updated_by = request.user
        item.save()
        audit(request, "update", "accounting.MonthlyFinancialTarget", item.pk, f"تحديث المتوقع الشهري لدورة {period_end}")
        messages.success(request, "تم حفظ المبلغ المتوقع لهذا الشهر المالي.")
        return redirect(f"/accounting/monthly-report/?period_end={period_end.isoformat()}")
    context = monthly_financial_report(school, period_end)
    context["target_form"] = target_form
    return render(request, "accounting/monthly_report.html", context)


@login_required
@management_required
def financial_year_close(request):
    school = active_school()
    form = FinancialYearClosureForm(request.POST or None, school=school)
    if request.method == "POST" and form.is_valid():
        try:
            closure = close_financial_year(
                school=school,
                source_year=form.cleaned_data["source_year"],
                target_year=form.cleaned_data["target_year"],
                user=request.user,
                notes=form.cleaned_data["notes"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            audit(request, "update", "accounting.FinancialYearClosure", closure.pk, f"إغلاق مالي وترحيل {closure.total_carried}")
            messages.success(request, f"تم الإغلاق المالي وترحيل {closure.total_carried} د.أ بنجاح.")
            return redirect("accounting:financial_year_close")
    closures = FinancialYearClosure.objects.filter(school=school).select_related("source_year", "target_year", "closed_by")
    return render(request, "accounting/financial_year_close.html", {"form": form, "closures": closures})


@login_required
@management_required
@require_POST
def invoice_cancel(request, invoice_id):
    invoice = get_object_or_404(StudentInvoice, pk=invoice_id)
    reason = request.POST.get("reason", "").strip()
    if invoice.payments.filter(status="posted").exists():
        messages.error(request, "يجب حذف جميع الدفعات المرتبطة بأمان قبل إلغاء الرسوم.")
    elif not reason:
        messages.error(request, "يجب كتابة سبب الإلغاء.")
    else:
        invoice.status = "cancelled"
        invoice.paid = False
        invoice.cancelled_by = request.user
        invoice.cancelled_at = timezone.now()
        invoice.cancellation_reason = reason
        invoice.save(update_fields=["status", "paid", "cancelled_by", "cancelled_at", "cancellation_reason", "updated_at"])
        audit(request, "update", "accounting.StudentInvoice", invoice.pk, f"إلغاء رسوم {invoice.invoice_number}: {reason}")
        messages.success(request, "تم إلغاء الرسوم.")
    return redirect("accounting:invoice_list")


@login_required
@management_required
def installment_list(request):
    items = Installment.objects.select_related("invoice", "invoice__student").all()
    for item in items:
        item.refresh_status()
    return render(request, "accounting/installment_list.html", {"items": items})


@login_required
@management_required
def installment_create(request):
    form = InstallmentForm(request.POST or None)
    if form.is_valid():
        installment = form.save()
        total = installment.invoice.installments.exclude(status="cancelled").aggregate(total=Sum("amount"))["total"] or Decimal("0")
        if total > installment.invoice.net_amount:
            installment.delete()
            form.add_error("amount", "مجموع الأقساط يتجاوز صافي الرسوم.")
        else:
            audit(request, "create", "accounting.Installment", installment.pk, f"إضافة قسط للطالب {installment.invoice.student.full_name}")
            messages.success(request, "تمت إضافة القسط.")
            return redirect("accounting:installment_list")
    return render(request, "accounting/form.html", {"form": form, "title": "إضافة قسط"})


@login_required
@management_required
def discount_list(request):
    items = DiscountRequest.objects.select_related("invoice", "invoice__student", "requested_by", "decided_by")
    return render(request, "accounting/discount_list.html", {"items": items})


@login_required
@management_required
def discount_create(request):
    form = DiscountRequestForm(request.POST or None)
    if form.is_valid():
        item = form.save(commit=False)
        item.requested_by = request.user
        item.full_clean()
        item.save()
        workflow = create_discount_workflow(item, request.user)
        audit(request, "create", "accounting.DiscountRequest", item.pk, f"طلب خصم مرتبط بالطلب #{workflow.pk}")
        messages.success(request, "تم إرسال طلب الخصم للموافقة.")
        return redirect("accounting:discount_list")
    return render(request, "accounting/form.html", {"form": form, "title": "طلب خصم"})


@login_required
@management_required
@require_POST
def discount_decide(request, pk):
    item = get_object_or_404(DiscountRequest, pk=pk)
    approve = request.POST.get("decision") == "approve"
    note = request.POST.get("note", "").strip()
    workflow = WorkflowRequest.objects.filter(
        related_app="accounting", related_model="DiscountRequest", related_object_id=str(item.pk)
    ).exclude(status__in=["approved", "rejected", "archived"]).order_by("-created_at").first()
    try:
        if workflow:
            transition_workflow(workflow, request.user, "approve" if approve else "reject", note)
        else:
            decide_discount(item, request.user, approve, note)
    except ValidationError as exc:
        messages.error(request, exc.message)
    else:
        audit(request, "update", "accounting.DiscountRequest", item.pk, f"{'اعتماد' if approve else 'رفض'} طلب الخصم")
        messages.success(request, "تم حفظ قرار الخصم وتحديث الطلب المرتبط.")
    return redirect("accounting:discount_list")


@login_required
@management_required
def student_statement(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    invoices = StudentInvoice.objects.filter(student=student).select_related("fee_category").prefetch_related("payments", "installments")
    payments = StudentPayment.objects.filter(invoice__student=student, status="posted").select_related("invoice")
    total_invoice = sum((i.net_amount for i in invoices if i.status != "cancelled"), Decimal("0"))
    total_payment = sum((p.amount for p in payments), Decimal("0"))
    return render(request, "accounting/student_statement.html", {
        "student": student,
        "invoices": invoices,
        "payments": payments,
        "total_invoice": total_invoice,
        "total_payment": total_payment,
        "remaining": max(total_invoice - total_payment, Decimal("0")),
    })


@login_required
@management_required
def receipt_print(request, receipt_id):
    receipt = get_object_or_404(Receipt, pk=receipt_id)
    audit(request, "print", "accounting.Receipt", receipt.pk, f"طباعة إيصال {receipt.receipt_number}")
    return FileResponse(receipt_pdf(receipt), as_attachment=False, filename=f"{receipt.receipt_number}.pdf")


@login_required
@management_required
def receipt_list(request):
    receipts = Receipt.objects.select_related("payment", "payment__invoice", "payment__invoice__student").all().order_by("-created_at")
    return render(request, "accounting/receipt_list.html", {"receipts": receipts})
