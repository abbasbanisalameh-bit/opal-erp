import base64
from io import BytesIO

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
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
from .services.generation import (
    candidate_values,
    create_issued_document,
    document_settings_for,
    guardian_payload,
    guardian_values,
    render_body,
    report_payload,
    student_values,
    teacher_values,
)


def _qr_data_uri(text):
    image = qrcode.make(text)
    stream = BytesIO()
    image.save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


@management_required
def document_list(request):
    documents = IssuedDocument.objects.select_related(
        "student", "teacher", "guardian", "candidate", "issued_by", "template"
    ).all()
    q = request.GET.get("q", "").strip()
    doc_type = request.GET.get("type", "").strip()
    status = request.GET.get("status", "").strip()
    if q:
        documents = documents.filter(
            Q(document_number__icontains=q)
            | Q(title__icontains=q)
            | Q(student__full_name__icontains=q)
            | Q(teacher__full_name__icontains=q)
            | Q(guardian__guardian_name__icontains=q)
            | Q(candidate__student_full_name__icontains=q)
            | Q(applicant_name__icontains=q)
        )
    if doc_type:
        documents = documents.filter(template__document_type=doc_type)
    if status:
        documents = documents.filter(status=status)
    return render(request, "documents/document_list.html", {
        "documents": documents[:500], "q": q, "selected_type": doc_type,
        "selected_status": status, "statuses": IssuedDocument.STATUS_CHOICES,
        "document_types": DocumentTemplate.DOCUMENT_TYPES,
    })


def _can_manage_templates(user):
    return user.is_superuser or user.is_staff


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


def _target_data(audience, target, extras=None):
    if audience == "student":
        school, enrollment, values = student_values(target, extras)
        return school or active_school(), values, enrollment
    if audience == "candidate":
        school, values = candidate_values(target, extras)
        return school, values, None
    if audience == "teacher":
        school, values = teacher_values(target, extras)
        return school, values, None
    school, students, year, values = guardian_values(target, extras)
    return school, values, (students, year)


def _issue_target(request, *, audience, target, back_url):
    templates = DocumentTemplate.objects.filter(audience=audience, is_active=True).order_by("name")
    selected = None
    requested = request.GET.get("template", "")
    if requested:
        selected = templates.filter(Q(code=requested) | Q(pk=requested if requested.isdigit() else None)).first()
    selected = selected or templates.first()
    extras = {
        "target_school": request.POST.get("target_school", "") or "المدرسة المحددة",
        "target_grade": request.POST.get("target_grade", "") or "الصف المحدد",
    }
    school, values, auxiliary = _target_data(audience, target, extras)
    initial = {}
    if selected:
        initial = {"template": selected, "title": selected.title, "content": render_body(selected, values)}
    form = IssueDocumentForm(request.POST or None, audience=audience, initial=initial)
    if request.method == "POST" and form.is_valid():
        template = form.cleaned_data["template"]
        # Recalculate the context after validation, but preserve the manager's editable body.
        payload = {}
        kwargs = {audience: target}
        if audience == "student" and template.document_type == "report_card":
            payload = report_payload(target, getattr(auxiliary, "academic_year", None))
        elif audience == "guardian" and template.document_type == "guardian_statement":
            students, year = auxiliary
            payload = guardian_payload(target, students, year)
        content = form.cleaned_data["content"]
        if template.document_type == "transfer_letter":
            content = content.replace("المدرسة المحددة", form.cleaned_data.get("target_school") or "المدرسة المحددة")
            content = content.replace("الصف المحدد", form.cleaned_data.get("target_grade") or "الصف المحدد")
        document = create_issued_document(
            template=template, title=form.cleaned_data["title"], content=content,
            user=request.user, school=school, payload=payload, **kwargs,
        )
        audit(request, "create", "documents.IssuedDocument", document.pk, f"إصدار {template.name} للمستفيد {document.applicant_name}")
        messages.success(request, f"تم إصدار الوثيقة رقم {document.document_number}.")
        return redirect("documents:document_detail", document_id=document.pk)
    return render(request, "documents/issue.html", {
        "form": form, "templates": templates, "selected": selected, "target": target,
        "audience": audience, "back_url": back_url,
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
        messages.success(request, "تم إلغاء الوثيقة وحفظ السبب دون حذف السجل.")
    return redirect("documents:document_detail", document_id=document.pk)


@management_required
@require_POST
def document_reissue(request, document_id):
    old = get_object_or_404(IssuedDocument, pk=document_id)
    new = create_issued_document(
        template=old.template, student=old.student, teacher=old.teacher, guardian=old.guardian,
        candidate=old.candidate, title=old.title, content=old.content, payload=old.payload,
        user=request.user, school=(
            getattr(old.teacher, "school", None) or getattr(old.guardian, "school", None)
            or getattr(old.candidate, "school", None)
            or (student_values(old.student)[0] if old.student_id else None) or active_school()
        ),
    )
    new.replaces = old
    new.save(update_fields=["replaces"])
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
