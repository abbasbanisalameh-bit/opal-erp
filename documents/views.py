import base64
from io import BytesIO

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from enterprise_ops.services import audit
from students.models import Student

from .forms import DocumentTemplateForm
from .models import DocumentTemplate, IssuedDocument, StudentIssuedDocument
from .services.pdf import student_certificate
from .utils import generate_document_number


def _qr_data_uri(text):
    image = qrcode.make(text)
    stream = BytesIO()
    image.save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


@login_required
def document_list(request):
    documents = IssuedDocument.objects.select_related("student", "issued_by", "template").all()
    q = request.GET.get("q", "").strip()
    doc_type = request.GET.get("type", "").strip()
    status = request.GET.get("status", "").strip()
    if q:
        documents = documents.filter(
            Q(document_number__icontains=q)
            | Q(title__icontains=q)
            | Q(student__full_name__icontains=q)
            | Q(applicant_name__icontains=q)
        )
    if doc_type:
        documents = documents.filter(template__document_type=doc_type)
    if status:
        documents = documents.filter(status=status)
    return render(request, "documents/document_list.html", {
        "documents": documents[:500],
        "q": q,
        "selected_type": doc_type,
        "selected_status": status,
        "statuses": IssuedDocument.STATUS_CHOICES,
    })


def _can_manage_templates(user):
    return user.is_superuser or user.is_staff


@login_required
def template_list(request):
    if not _can_manage_templates(request.user):
        messages.error(request, "هذه الشاشة متاحة لإدارة النظام فقط.")
        return redirect("documents:document_list")
    form = DocumentTemplateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        audit(request, "create", "documents.DocumentTemplate", item.pk, f"إضافة قالب وثيقة {item.name}")
        messages.success(request, "تم حفظ قالب الوثيقة من واجهة OPAL.")
        return redirect("documents:template_list")
    return render(request, "documents/template_list.html", {"form": form, "items": DocumentTemplate.objects.all()})


@login_required
def template_update(request, pk):
    if not _can_manage_templates(request.user):
        messages.error(request, "هذه الشاشة متاحة لإدارة النظام فقط.")
        return redirect("documents:document_list")
    item = get_object_or_404(DocumentTemplate, pk=pk)
    form = DocumentTemplateForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit(request, "update", "documents.DocumentTemplate", item.pk, f"تعديل قالب وثيقة {item.name}")
        messages.success(request, "تم تعديل قالب الوثيقة.")
        return redirect("documents:template_list")
    return render(request, "documents/template_form.html", {"form": form, "title": "تعديل قالب وثيقة"})


@login_required
def document_detail(request, document_id):
    document = get_object_or_404(IssuedDocument.objects.select_related("student", "issued_by", "template", "cancelled_by", "replaces"), pk=document_id)
    verification_url = request.build_absolute_uri(reverse("documents:verify", args=[document.document_number, document.verification_code]))
    return render(request, "documents/document_detail.html", {"document": document, "qr_data_uri": _qr_data_uri(verification_url), "verification_url": verification_url})


@login_required
@require_POST
def document_cancel(request, document_id):
    document = get_object_or_404(IssuedDocument, pk=document_id)
    reason = request.POST.get("reason", "").strip()
    if document.status == "cancelled":
        messages.info(request, "الوثيقة ملغاة مسبقًا.")
    elif not reason:
        messages.error(request, "يجب كتابة سبب إلغاء الوثيقة.")
    else:
        document.status = "cancelled"
        document.cancelled_by = request.user
        document.cancelled_at = timezone.now()
        document.cancellation_reason = reason
        document.save(update_fields=["status", "cancelled_by", "cancelled_at", "cancellation_reason"])
        audit(request, "update", "documents.IssuedDocument", document.pk, f"إلغاء وثيقة {document.document_number}: {reason}")
        messages.success(request, "تم إلغاء الوثيقة وحفظ السبب.")
    return redirect("documents:document_detail", document_id=document.pk)


@login_required
@require_POST
def document_reissue(request, document_id):
    old = get_object_or_404(IssuedDocument, pk=document_id)
    new = IssuedDocument.objects.create(
        template=old.template,
        student=old.student,
        applicant_name=old.applicant_name,
        document_number=generate_document_number(),
        title=old.title,
        content=old.content,
        issued_by=request.user,
        replaces=old,
    )
    if new.student_id:
        StudentIssuedDocument.objects.get_or_create(student=new.student, issued_document=new)
    audit(request, "create", "documents.IssuedDocument", new.pk, f"إعادة إصدار بدل الوثيقة {old.document_number}")
    messages.success(request, f"تم إصدار وثيقة بديلة برقم {new.document_number}.")
    return redirect("documents:document_detail", document_id=new.pk)


def verify_document(request, document_number, verification_code):
    document = get_object_or_404(
        IssuedDocument.objects.select_related("student", "template"),
        document_number=document_number,
        verification_code=verification_code,
    )
    return render(request, "documents/verify.html", {"document": document})


@login_required
def issue_student_certificate(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    number = generate_document_number()
    document = IssuedDocument.objects.create(
        student=student,
        applicant_name=student.full_name,
        document_number=number,
        title="إثبات طالب",
        content=f"تشهد المدرسة بأن الطالب {student.full_name} مسجل لديها.",
        issued_by=request.user,
    )
    StudentIssuedDocument.objects.get_or_create(student=student, issued_document=document)
    audit(request, "create", "documents.IssuedDocument", document.pk, f"إصدار إثبات طالب {student.full_name}")
    return FileResponse(student_certificate(student, number), filename=f"{number}.pdf", content_type="application/pdf")
