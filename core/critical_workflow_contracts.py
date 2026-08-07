"""Read-only contracts for OPAL's highest-risk operational workflows.

Update 124 protects the parent communication channel, teacher service lifecycle,
and receipt printing rules introduced in Update 123.  Static checks can run from
``manage.py check`` without touching school data; the data audit is exposed by a
separate management command.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.urls import NoReverseMatch, reverse

from .final_reengineering_audit import AuditIssue, project_root


_REQUIRED_ROUTES = (
    ("parent_portal:dashboard", (), {}),
    ("parent_portal:account", (), {}),
    ("enterprise_ops:feedback_list", (), {}),
    ("enterprise_ops:feedback_create", (), {}),
    ("teachers:teacher_detail", (1,), {}),
    ("teachers:teacher_toggle", (1,), {}),
    ("teachers:teacher_terminate", (1,), {}),
    ("documents:document_detail", (), {"document_id": 1}),
    ("admissions:registration_receipt", (), {"pk": 1}),
    ("admissions:fee_payment_receipt", (), {"pk": 1}),
)


def _read(root: Path, relative: str) -> tuple[str, list[AuditIssue]]:
    path = root / relative
    if not path.is_file():
        return "", [AuditIssue("critical_file_missing", f"ملف المسار الحرج مفقود: {relative}", relative)]
    try:
        return path.read_text(encoding="utf-8"), []
    except (OSError, UnicodeDecodeError) as exc:
        return "", [AuditIssue("critical_file_unreadable", f"تعذر قراءة {relative}: {exc}", relative)]


def audit_critical_routes() -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    for route, args, kwargs in _REQUIRED_ROUTES:
        try:
            reverse(route, args=args, kwargs=kwargs)
        except NoReverseMatch:
            issues.append(AuditIssue("critical_route_unresolved", f"المسار الحرج غير قابل للحل: {route}"))
    return issues


def audit_parent_communication_contract(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    issues: list[AuditIssue] = []

    sources: dict[str, str] = {}
    for relative in (
        "parent_portal/forms.py",
        "parent_portal/middleware.py",
        "enterprise_ops/permissions.py",
        "enterprise_ops/views.py",
        "templates/parent_portal/dashboard.html",
        "templates/enterprise_ops/feedback_list.html",
    ):
        text, read_issues = _read(root, relative)
        sources[relative] = text
        issues.extend(read_issues)

    forms = sources["parent_portal/forms.py"]
    family_match = re.search(
        r"class\s+ParentFamilyPersonalForm\b(?P<body>.*?)(?=\nclass\s+|\Z)",
        forms,
        flags=re.S,
    )
    if not family_match:
        issues.append(AuditIssue("parent_personal_form_missing", "نموذج بيانات ولي الأمر الشخصية غير موجود.", "parent_portal/forms.py"))
    else:
        body = family_match.group("body")
        fields_match = re.search(r"fields\s*=\s*\[(?P<fields>.*?)\]", body, flags=re.S)
        if not fields_match:
            issues.append(AuditIssue("parent_personal_fields_missing", "تعذر تحديد حقول نموذج ولي الأمر.", "parent_portal/forms.py"))
        elif re.search(r"['\"]photo['\"]", fields_match.group("fields")):
            issues.append(AuditIssue("parent_photo_field_mixed", "حقل الصورة عاد إلى نموذج بيانات الأسرة وقد يعيد خطأ 500.", "parent_portal/forms.py"))
    if "class ParentPhotoForm" not in forms or 'fields = ["photo"]' not in forms:
        issues.append(AuditIssue("parent_photo_form_missing", "نموذج الصورة المستقل لولي الأمر غير مكتمل.", "parent_portal/forms.py"))

    middleware = sources["parent_portal/middleware.py"]
    if '"/enterprise/feedback/"' not in middleware:
        issues.append(AuditIssue("parent_feedback_middleware", "بوابة الشكاوى غير مستثناة من حصر مسارات حساب ولي الأمر.", "parent_portal/middleware.py"))

    permissions = sources["enterprise_ops/permissions.py"]
    for token, message in (
        ('feature == "workflow"', "قناة الشكاوى ليست محمية بعقد صلاحية مستقل."),
        ('code in {"teacher", "parent"}', "المعلم وولي الأمر غير مثبتين ضمن صلاحية الإرسال."),
    ):
        if token not in permissions:
            issues.append(AuditIssue("feedback_permission_contract", message, "enterprise_ops/permissions.py"))

    view = sources["enterprise_ops/views.py"]
    for token, message in (
        ("def feedback_list", "الصفحة الموحدة للشكاوى والاقتراحات غير موجودة."),
        ("FeedbackTicketForm(request.POST or None)", "نموذج الإرسال غير مربوط بصفحة الشكاوى الموحدة."),
        ("item.sender = request.user", "مرسل الشكوى لا يُثبت من الحساب الحالي."),
        ('return redirect("enterprise_ops:feedback_list")', "إعادة التوجيه إلى المصدر الموحد غير موجودة."),
    ):
        if token not in view:
            issues.append(AuditIssue("feedback_view_contract", message, "enterprise_ops/views.py"))

    dashboard = sources["templates/parent_portal/dashboard.html"]
    if "enterprise_ops:feedback_list" not in dashboard or "إرسال شكوى أو اقتراح" not in dashboard:
        issues.append(AuditIssue("parent_feedback_card", "بطاقة أو زر الشكاوى والاقتراحات غير موجود في لوحة ولي الأمر.", "templates/parent_portal/dashboard.html"))

    template = sources["templates/enterprise_ops/feedback_list.html"]
    for token, message in (
        ('method="post"', "نموذج الشكوى لا يستخدم POST."),
        ("{% csrf_token %}", "نموذج الشكوى لا يحتوي حماية CSRF."),
        ('id="feedback-submit-button"', "زر الإرسال الصريح غير موجود."),
        ("إرسال إلى الإدارة", "نص زر الإرسال غير واضح للمستخدم."),
    ):
        if token not in template:
            issues.append(AuditIssue("feedback_template_contract", message, "templates/enterprise_ops/feedback_list.html"))
    return issues


def audit_teacher_lifecycle_contract(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    issues: list[AuditIssue] = []
    sources: dict[str, str] = {}
    for relative in (
        "teachers/forms.py",
        "teachers/views.py",
        "teachers/payroll_views.py",
        "teachers/payroll_services.py",
        "templates/teachers/teacher_detail.html",
        "documents/defaults.py",
        "documents/workflow.py",
    ):
        text, read_issues = _read(root, relative)
        sources[relative] = text
        issues.extend(read_issues)

    forms = sources["teachers/forms.py"]
    if "class TeacherTerminationForm" not in forms or "إنهاء خدمة المعلم" not in forms:
        issues.append(AuditIssue("termination_form_contract", "نموذج إنهاء الخدمة أو عبارة تأكيده غير موجودة.", "teachers/forms.py"))
    teacher_form_match = re.search(r"class\s+TeacherForm\b(?P<body>.*?)(?=\nclass\s+|\Z)", forms, flags=re.S)
    if teacher_form_match:
        body = teacher_form_match.group("body")
        fields_match = re.search(r"fields\s*=\s*\[(?P<fields>.*?)\]", body, flags=re.S)
        fields_text = fields_match.group("fields") if fields_match else ""
        for forbidden in ("is_active", "end_date", "end_reason"):
            if re.search(rf"['\"]{forbidden}['\"]", fields_text):
                issues.append(AuditIssue("teacher_lifecycle_bypass", f"الحقل {forbidden} موجود في نموذج التعديل العام ويتجاوز دورة الخدمة الرسمية.", "teachers/forms.py"))

    service = sources["teachers/payroll_services.py"]
    required_service_tokens = (
        "@transaction.atomic",
        "select_for_update()",
        "issue_teacher_termination_document",
        ".update(is_active=False)",
        'teacher.user.is_active = False',
        "def reactivate_teacher",
        'teacher.user.is_active = True',
        '"assignments_reactivated": 0',
        '"timetable_reactivated": 0',
    )
    for token in required_service_tokens:
        if token not in service:
            issues.append(AuditIssue("teacher_lifecycle_service", f"عقد دورة خدمة المعلم يفتقد: {token}", "teachers/payroll_services.py"))

    payroll_view = sources["teachers/payroll_views.py"]
    for token in ("def teacher_terminate", "TeacherTerminationForm", "terminate_teacher(", 'redirect("documents:document_detail"'):
        if token not in payroll_view:
            issues.append(AuditIssue("teacher_termination_view", f"مسار إنهاء الخدمة يفتقد: {token}", "teachers/payroll_views.py"))

    teacher_views = sources["teachers/views.py"]
    if "reactivate_teacher" not in teacher_views or "teacher_toggle" not in teacher_views:
        issues.append(AuditIssue("teacher_reactivation_view", "إعادة التفعيل الرسمية غير مرتبطة بملف المعلم.", "teachers/views.py"))

    detail = sources["templates/teachers/teacher_detail.html"]
    for token, message in (
        ("teacher_terminate", "زر إنهاء الخدمة غير موجود في ملف المعلم."),
        ("teacher_toggle", "زر إعادة التفعيل غير موجود في ملف المعلم."),
        ("issued_documents", "أرشيف الوثائق الصادرة غير ظاهر في ملف المعلم."),
        ("latest_termination_document", "رابط مباشر لآخر كتاب إنهاء خدمة غير موجود."),
    ):
        if token not in detail:
            issues.append(AuditIssue("teacher_detail_lifecycle", message, "templates/teachers/teacher_detail.html"))

    defaults = sources["documents/defaults.py"]
    workflow = sources["documents/workflow.py"]
    if '"code": "teacher-termination"' not in defaults:
        issues.append(AuditIssue("termination_template_missing", "قالب كتاب إنهاء الخدمة الرسمي غير موجود.", "documents/defaults.py"))
    if "def issue_teacher_termination_document" not in workflow or '"kind": "teacher_termination"' not in workflow:
        issues.append(AuditIssue("termination_document_workflow", "إصدار كتاب إنهاء الخدمة غير مثبت في محرك الوثائق الرسمي.", "documents/workflow.py"))
    return issues


def audit_receipt_print_contract(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    issues: list[AuditIssue] = []
    template_paths = (
        "templates/admissions/registration_receipt.html",
        "templates/admissions/fee_payment_receipt.html",
    )
    for relative in template_paths:
        text, read_issues = _read(root, relative)
        issues.extend(read_issues)
        if not text:
            continue
        checks = (
            ('{% extends "base/base.html" %}', False, "الإيصال يرث قشرة النظام العامة."),
            ('{% include "includes/sidebar.html" %}', False, "الإيصال يضم القائمة الجانبية."),
            ('{% include "includes/topbar.html" %}', False, "الإيصال يضم الشريط العلوي."),
            ("{% for copy_title in receipt_copies %}", True, "حلقة النسختين غير موجودة."),
            ("size:A4 landscape", True, "حجم الطباعة ليس A4 أفقيًا."),
            ("grid-template-columns:1fr 1fr", True, "النسختان لا تظهران جنبًا إلى جنب."),
            (".screen-toolbar{display:none!important}", True, "شريط الأزرار لا يختفي عند الطباعة."),
            ("width:297mm", True, "عرض صفحة A4 الأفقي غير مثبت."),
            ("height:210mm", True, "ارتفاع صفحة A4 الأفقي غير مثبت."),
        )
        for token, required, message in checks:
            present = token in text
            if present != required:
                issues.append(AuditIssue("receipt_print_contract", message, relative))

    views, read_issues = _read(root, "admissions/views.py")
    issues.extend(read_issues)
    if views.count('"receipt_copies": ["نسخة المدرسة", "نسخة ولي الأمر"]') < 2:
        issues.append(AuditIssue("receipt_copy_context", "مسارا الإيصال لا يرسلان نسختي المدرسة وولي الأمر.", "admissions/views.py"))

    pdf, read_issues = _read(root, "accounting/services/pdf.py")
    issues.extend(read_issues)
    for token, message in (
        ("landscape(A4)", "الإيصال PDF القديم ليس A4 أفقيًا."),
        ('copy_label="SCHOOL COPY"', "نسخة المدرسة مفقودة من PDF القديم."),
        ('copy_label="GUARDIAN COPY"', "نسخة ولي الأمر مفقودة من PDF القديم."),
    ):
        if token not in pdf:
            issues.append(AuditIssue("legacy_receipt_pdf", message, "accounting/services/pdf.py"))
    if pdf.count("pdf.showPage()") != 1:
        issues.append(AuditIssue("legacy_receipt_pages", "مولد PDF يجب أن ينهي صفحة واحدة فقط للإيصال ذي النسختين.", "accounting/services/pdf.py"))
    return issues


def run_critical_workflow_contract_audit(root: Path | None = None) -> dict:
    root = (root or project_root()).resolve()
    checks = {
        "critical_routes": audit_critical_routes(),
        "parent_communication": audit_parent_communication_contract(root=root),
        "teacher_lifecycle": audit_teacher_lifecycle_contract(root=root),
        "receipt_printing": audit_receipt_print_contract(root=root),
    }
    issues = [issue for group in checks.values() for issue in group]
    return {
        "ok": not issues,
        "checks": {name: not group for name, group in checks.items()},
        "issue_count": len(issues),
        "issues": [issue.as_dict() for issue in issues],
    }


def audit_critical_workflow_data() -> dict:
    """Inspect live data invariants without changing any record."""
    from django.db.models import Count

    from documents.models import IssuedDocument
    from parent_portal.models import Family
    from teachers.models import Teacher, TeacherAssignment
    from timetable.models import TimetableEntry

    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def add(target, code, message):
        target.append({"code": code, "message": message})

    for family in Family.objects.select_related("user", "merged_into").filter(is_active=True):
        if family.merged_into_id:
            add(errors, "PARENT_ACTIVE_MERGED_FAMILY", f"ملف ولي الأمر #{family.pk} فعال رغم دمجه في ملف آخر.")
        if family.user_id and not family.user.is_active:
            add(warnings, "PARENT_INACTIVE_ACCOUNT", f"ملف ولي الأمر #{family.pk} مرتبط بحساب دخول غير فعال.")

    termination_docs = set(
        IssuedDocument.objects.filter(template__code="teacher-termination", teacher_id__isnull=False)
        .values_list("teacher_id", flat=True)
    )
    assignment_counts = {
        row["teacher_id"]: row["total"]
        for row in TeacherAssignment.objects.filter(is_active=True, academic_year__is_closed=False)
        .values("teacher_id")
        .annotate(total=Count("id"))
    }
    timetable_counts = {
        row["teacher_id"]: row["total"]
        for row in TimetableEntry.objects.filter(is_active=True, academic_year__is_closed=False)
        .values("teacher_id")
        .annotate(total=Count("id"))
    }
    teachers = Teacher.objects.select_related("user").all()
    for teacher in teachers:
        label = f"المعلم #{teacher.pk} ({teacher.full_name})"
        if teacher.is_active:
            if teacher.end_date or (teacher.end_reason or "").strip():
                add(errors, "TEACHER_ACTIVE_WITH_TERMINATION", f"{label} نشط وتوجد عليه بيانات انتهاء خدمة.")
            if teacher.user_id and not teacher.user.is_active:
                add(warnings, "TEACHER_ACTIVE_INACTIVE_LOGIN", f"{label} نشط لكن حساب الدخول غير فعال.")
            continue

        if teacher.user_id and teacher.user.is_active:
            add(errors, "TEACHER_INACTIVE_ACTIVE_LOGIN", f"{label} غير نشط لكن حساب الدخول ما زال فعالًا.")
        active_assignments = assignment_counts.get(teacher.pk, 0)
        if active_assignments:
            add(errors, "TEACHER_INACTIVE_ASSIGNMENTS", f"{label} لديه {active_assignments} تكليفًا فعالًا في أعوام مفتوحة.")
        active_timetable = timetable_counts.get(teacher.pk, 0)
        if active_timetable:
            add(errors, "TEACHER_INACTIVE_TIMETABLE", f"{label} لديه {active_timetable} حصة فعالة في أعوام مفتوحة.")

        if teacher.end_date:
            if not (teacher.end_reason or "").strip():
                add(errors, "TEACHER_TERMINATION_REASON_MISSING", f"{label} منتهي الخدمة دون سبب محفوظ.")
            if teacher.pk not in termination_docs:
                add(warnings, "TEACHER_TERMINATION_DOCUMENT_MISSING", f"{label} منتهي الخدمة ولا يوجد كتاب إنهاء خدمة مؤرشف؛ قد يكون سجلًا قديمًا قبل Update 123.")
        else:
            add(warnings, "TEACHER_INACTIVE_WITHOUT_TERMINATION", f"{label} غير نشط دون تاريخ إنهاء خدمة؛ راجع سبب الإيقاف القديم.")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": {"errors": len(errors), "warnings": len(warnings)},
        "safety": {"read_only": True, "database_modified": False},
    }
