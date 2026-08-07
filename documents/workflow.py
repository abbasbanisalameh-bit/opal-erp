"""Canonical document lifecycle services for OPAL ERP.

This module owns the stable internal workflow for document discovery, issuance,
cancellation, verification context, and replacement issuance. Views remain thin
and the existing models/templates/URLs keep their current behavior.
"""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from admissions.services import active_school

from .models import DocumentTemplate, IssuedDocument
from .services.generation import (
    create_issued_document,
    guardian_payload,
    guardian_values,
    render_body,
    report_payload,
    student_values,
    teacher_values,
)


def build_document_list_context(*, query="", document_type="", status=""):
    """Build the canonical archive context without changing current filters."""
    documents = IssuedDocument.objects.select_related(
        "student", "teacher", "guardian", "issued_by", "template"
    ).all()
    query = (query or "").strip()
    document_type = (document_type or "").strip()
    status = (status or "").strip()
    if query:
        documents = documents.filter(
            Q(document_number__icontains=query)
            | Q(title__icontains=query)
            | Q(student__full_name__icontains=query)
            | Q(teacher__full_name__icontains=query)
            | Q(guardian__guardian_name__icontains=query)
            | Q(applicant_name__icontains=query)
        )
    if document_type:
        documents = documents.filter(template__document_type=document_type)
    if status:
        documents = documents.filter(status=status)
    return {
        "documents": documents[:500],
        "q": query,
        "selected_type": document_type,
        "selected_status": status,
        "statuses": IssuedDocument.STATUS_CHOICES,
        "document_types": DocumentTemplate.DOCUMENT_TYPES,
    }


def build_target_data(*, audience, target, extras=None):
    """Return the school, template values, and auxiliary payload source."""
    if audience == "student":
        school, enrollment, values = student_values(target, extras)
        return school or active_school(), values, enrollment
    if audience == "teacher":
        school, values = teacher_values(target, extras)
        return school, values, None
    school, students, year, values = guardian_values(target, extras)
    return school, values, (students, year)


def build_issue_context(*, audience, target, requested_template="", extras=None):
    templates = DocumentTemplate.objects.filter(audience=audience, is_active=True).order_by("name")
    selected = None
    requested_template = (requested_template or "").strip()
    if requested_template:
        selected = templates.filter(
            Q(code=requested_template)
            | Q(pk=requested_template if requested_template.isdigit() else None)
        ).first()
    selected = selected or templates.first()
    school, values, auxiliary = build_target_data(audience=audience, target=target, extras=extras)
    initial = {}
    if selected:
        initial = {
            "template": selected,
            "title": selected.title,
            "content": render_body(selected, values),
        }
    return {
        "templates": templates,
        "selected": selected,
        "school": school,
        "auxiliary": auxiliary,
        "initial": initial,
    }


def _payload_for(*, audience, target, template, auxiliary):
    if audience == "student" and template.document_type == "report_card":
        return report_payload(target, getattr(auxiliary, "academic_year", None))
    if audience == "guardian" and template.document_type == "guardian_statement":
        students, year = auxiliary
        return guardian_payload(target, students, year)
    return {}


@transaction.atomic
def issue_document_from_form(*, form, audience, target, school, auxiliary, user):
    """Issue one canonical snapshot document from a validated form."""
    template = form.cleaned_data["template"]
    content = form.cleaned_data["content"]
    if template.document_type == "transfer_letter":
        content = content.replace(
            "المدرسة المحددة", form.cleaned_data.get("target_school") or "المدرسة المحددة"
        )
        content = content.replace(
            "الصف المحدد", form.cleaned_data.get("target_grade") or "الصف المحدد"
        )
    return create_issued_document(
        template=template,
        title=form.cleaned_data["title"],
        content=content,
        user=user,
        school=school,
        payload=_payload_for(
            audience=audience, target=target, template=template, auxiliary=auxiliary
        ),
        **{audience: target},
    )


@transaction.atomic
def cancel_issued_document(*, document, reason, user):
    """Cancel without deleting history; returns a stable result code."""
    reason = (reason or "").strip()
    if document.status == "cancelled":
        return "already_cancelled"
    if not reason:
        return "reason_required"
    document.status = "cancelled"
    document.cancelled_by = user
    document.cancelled_at = timezone.now()
    document.cancellation_reason = reason
    document.save(
        update_fields=["status", "cancelled_by", "cancelled_at", "cancellation_reason"]
    )
    return "cancelled"



@transaction.atomic
def issue_teacher_termination_document(*, teacher, user):
    """Issue the canonical termination letter after service termination.

    The template is created lazily so existing installations need no data
    migration.  The issued document is an immutable snapshot linked to the
    teacher and remains in the archive if the teacher is later reactivated.
    """
    from .defaults import DEFAULT_DOCUMENT_TEMPLATES

    definition = next(
        item for item in DEFAULT_DOCUMENT_TEMPLATES
        if item["code"] == "teacher-termination"
    )
    template, _ = DocumentTemplate.objects.get_or_create(
        code=definition["code"],
        defaults={
            "audience": definition["audience"],
            "document_type": definition["document_type"],
            "name": definition["name"],
            "title": definition["title"],
            "body": definition["body"],
            "is_active": True,
        },
    )
    school, values = teacher_values(teacher)
    return create_issued_document(
        template=template,
        teacher=teacher,
        title=template.title,
        content=render_body(template, values),
        payload={
            "kind": "teacher_termination",
            "teacher_id": teacher.pk,
            "employee_number": teacher.employee_number,
            "end_date": str(teacher.end_date or ""),
            "reason": teacher.end_reason,
        },
        user=user,
        school=school,
    )

def resolve_document_school(document):
    return (
        getattr(document.teacher, "school", None)
        or getattr(document.guardian, "school", None)
        or (student_values(document.student)[0] if document.student_id else None)
        or active_school()
    )


@transaction.atomic
def reissue_document(*, original, user):
    """Create an immutable replacement snapshot linked to the original."""
    replacement = create_issued_document(
        template=original.template,
        student=original.student,
        teacher=original.teacher,
        guardian=original.guardian,
        title=original.title,
        content=original.content,
        payload=original.payload,
        user=user,
        school=resolve_document_school(original),
    )
    replacement.replaces = original
    replacement.save(update_fields=["replaces"])
    return replacement


__all__ = [
    "build_document_list_context",
    "build_issue_context",
    "build_target_data",
    "cancel_issued_document",
    "issue_document_from_form",
    "issue_teacher_termination_document",
    "reissue_document",
    "resolve_document_school",
]
