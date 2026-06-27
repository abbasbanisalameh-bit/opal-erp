from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import FeeCategory, StudentInvoice, StudentPayment
from .forms import FeeCategoryForm, StudentInvoiceForm, StudentPaymentForm
from academics.models import StudentRecord


@login_required
def finance_dashboard(request):
    invoices = StudentInvoice.objects.all()
    payments = StudentPayment.objects.all()

    total_invoices = sum(i.amount for i in invoices)
    total_payments = sum(p.amount for p in payments)
    remaining = total_invoices - total_payments

    return render(request, "accounting/dashboard.html", {
        "total_invoices": total_invoices,
        "total_payments": total_payments,
        "remaining": remaining,
        "invoices_count": invoices.count(),
        "payments_count": payments.count(),
    })


@login_required
def invoice_list(request):
    invoices = StudentInvoice.objects.select_related("student", "fee_category").all()
    return render(request, "accounting/invoice_list.html", {"invoices": invoices})


@login_required
def invoice_create(request):
    form = StudentInvoiceForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("accounting:invoice_list")
    return render(request, "accounting/form.html", {"form": form, "title": "إصدار فاتورة"})


@login_required
def payment_create(request):
    form = StudentPaymentForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("accounting:invoice_list")
    return render(request, "accounting/form.html", {"form": form, "title": "تسجيل دفعة"})


@login_required
def student_statement(request, student_id):
    student = get_object_or_404(StudentRecord, pk=student_id)

    invoices = StudentInvoice.objects.filter(student=student)
    payments = StudentPayment.objects.filter(invoice__student=student)

    total_invoice = sum(i.amount for i in invoices)
    total_payment = sum(p.amount for p in payments)

    return render(
        request,
        "accounting/student_statement.html",
        {
            "student": student,
            "invoices": invoices,
            "payments": payments,
            "total_invoice": total_invoice,
            "total_payment": total_payment,
            "remaining": total_invoice - total_payment,
        },
    )

from django.http import FileResponse
from accounting.services.pdf import receipt_pdf


@login_required
def receipt_print(request, receipt_id):
    receipt = get_object_or_404(Receipt, pk=receipt_id)
    return FileResponse(
        receipt_pdf(receipt),
        as_attachment=False,
        filename=f"{receipt.receipt_number}.pdf",
    )

