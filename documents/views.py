import base64
from io import BytesIO

import qrcode
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from admissions.models import AdmissionApplication
from admissions.services import active_school
from enterprise_ops.permissions import management_required
from enterprise_ops.services import audit
from parent_portal.models import Family
from students.models import Student
from teachers.models import Teacher

from .forms import DocumentSettingsForm, DocumentTemplateForm, IssueDocumentForm
from .models import DocumentSettings, DocumentTemplate, IssuedDocument, StudentIssuedDocument
from .services.generation import document_settings_for
from .workflow import (
    build_document_list_context,
    build_issue_context,
    cancel_issued_document,
    issue_document_from_form,
    reissue_document,
)


def _qr_data_uri(text):
    image = qrcode.make(text)
    stream = BytesIO()
    image.save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


@management_required
def document_list(request):
    context = build_document_list_context(
        query=request.GET.get("q", ""),
        document_type=request.GET.get("type", ""),
        status=request.GET.get("status", ""),
    )
    return render(request, "documents/document_list.html", context)


@management_required
def template_list(request):
    form = DocumentTemplateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        audit(request, "create", "documents.DocumentTemplate", item.pk, f"إضافة قالب وثيقة {item.name}")
        messages.success(request, "تم حفظ قالب الوثيقة. ويمكن للمدير تعديل نصه الافتراضي في أي وقت.")
        return redirect("documents:template_list")
    return render(request, "documents/template_list.html", {"form": form, "items": DocumentTemplate.objects.all()})


@management_required
def template_update(request, pk):
    item = get_object_or_404(DocumentTemplate, pk=pk)
    form = DocumentTemplateForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit(request, "update", "documents.DocumentTemplate", item.pk, f"تعديل قالب وثيقة {item.name}")
        messages.success(request, "تم تعديل النص الافتراضي للقالب، ولن تتغير الوثائق الصادرة سابقًا.")
        return redirect("documents:template_list")
    return render(request, "documents/template_form.html", {"form": form, "title": "تعديل قالب وثيقة"})


@management_required
def document_settings(request):
    school = active_school()
    item = document_settings_for(school)
    form = DocumentSettingsForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        settings = form.save(commit=False)
        settings.updated_by = request.user
        settings.save()
        audit(request, "update", "documents.DocumentSettings", settings.pk, "تحديث توقيع وختم الوثائق")
        messages.success(request, "تم حفظ اسم المدير العام وبيانات التوقيع والختم.")
        return redirect("documents:settings")
    return render(request, "documents/settings.html", {"form": form, "school": school})


def _issue_target(request, *, audience, target, back_url):
    extras = {
        "target_school": request.POST.get("target_school", "") or "المدرسة المحددة",
        "target_grade": request.POST.get("target_grade", "") or "الصف المحدد",
    }
    issue_context = build_issue_context(
        audience=audience,
        target=target,
        requested_template=request.GET.get("template", ""),
        extras=extras,
    )
    form = IssueDocumentForm(
        request.POST or None, audience=audience, initial=issue_context["initial"]
    )
    if request.method == "POST" and form.is_valid():
        document = issue_document_from_form(
            form=form,
            audience=audience,
            target=target,
            school=issue_context["school"],
            auxiliary=issue_context["auxiliary"],
            user=request.user,
        )
        audit(
            request, "create", "documents.IssuedDocument", document.pk,
            f"إصدار {document.template.name} للمستفيد {document.applicant_name}"
        )
        messages.success(request, f"تم إصدار الوثيقة رقم {document.document_number}.")
        return redirect("documents:document_detail", document_id=document.pk)
    return render(request, "documents/issue.html", {
        "form": form,
        "templates": issue_context["templates"],
        "selected": issue_context["selected"],
        "target": target,
        "audience": audience,
        "back_url": back_url,
    })


@management_required
def issue_student(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    return _issue_target(request, audience="student", target=student, back_url=reverse("students:student_360", args=[student.pk]))


@management_required
def issue_candidate(request, candidate_id):
    candidate = get_object_or_404(AdmissionApplication, pk=candidate_id, status="candidate")
    return _issue_target(request, audience="candidate", target=candidate, back_url=reverse("admissions:candidate_detail", args=[candidate.pk]))


@management_required
def issue_teacher(request, teacher_id):
    teacher = get_object_or_404(Teacher, pk=teacher_id)
    return _issue_target(request, audience="teacher", target=teacher, back_url=reverse("teachers:teacher_detail", args=[teacher.pk]))


@management_required
def issue_guardian(request, guardian_id):
    guardian = get_object_or_404(Family, pk=guardian_id, is_active=True)
    return _issue_target(request, audience="guardian", target=guardian, back_url=reverse("parent_portal:family_detail", args=[guardian.pk]))


@management_required
def document_detail(request, document_id):
    document = get_object_or_404(
        IssuedDocument.objects.select_related(
            "student", "teacher", "guardian", "candidate", "issued_by", "template",
            "cancelled_by", "replaces"
        ), pk=document_id,
    )
    verification_url = request.build_absolute_uri(reverse("documents:verify", args=[document.document_number, document.verification_code]))
    return render(request, "documents/document_detail.html", {
        "document": document, "qr_data_uri": _qr_data_uri(verification_url),
        "verification_url": verification_url,
    })


@management_required
@require_POST
def document_cancel(request, document_id):
    document = get_object_or_404(IssuedDocument, pk=document_id)
    reason = request.POST.get("reason", "").strip()
    result = cancel_issued_document(document=document, reason=reason, user=request.user)
    if result == "already_cancelled":
        messages.info(request, "الوثيقة ملغاة مسبقًا.")
    elif result == "reason_required":
        messages.error(request, "يجب كتابة سبب إلغاء الوثيقة.")
    else:
        audit(request, "update", "documents.IssuedDocument", document.pk, f"إلغاء وثيقة {document.document_number}: {reason}")
        messages.success(request, "تم إلغاء الوثيقة وحفظ السبب دون حذف السجل.")
    return redirect("documents:document_detail", document_id=document.pk)


@management_required
@require_POST
def document_reissue(request, document_id):
    old = get_object_or_404(IssuedDocument, pk=document_id)
    new = reissue_document(original=old, user=request.user)
    audit(request, "create", "documents.IssuedDocument", new.pk, f"إعادة إصدار بدل الوثيقة {old.document_number}")
    messages.success(request, f"تم إصدار وثيقة بديلة برقم {new.document_number}.")
    return redirect("documents:document_detail", document_id=new.pk)


def verify_document(request, document_number, verification_code):
    document = get_object_or_404(
        IssuedDocument.objects.select_related("student", "teacher", "guardian", "candidate", "template"),
        document_number=document_number, verification_code=verification_code,
    )
    return render(request, "documents/verify.html", {"document": document})


@management_required
def issue_student_certificate(request, student_id):
    """Compatibility route retained for bookmarks and older buttons."""
    return redirect(f"{reverse('documents:issue_student', args=[student_id])}?template=student-proof")
