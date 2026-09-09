"""Static contracts for OPAL's single-entry role architecture.

Update 125 does not remove routes, pages, templates, or business services.  It
limits visible navigation to one approved gateway for each role and keeps
legacy/detail routes available only inside their owning workflow.
"""

from __future__ import annotations

from pathlib import Path
import re

from .final_reengineering_audit import AuditIssue, project_root
from .workflow_catalog import AUTHENTICATED, DRIVER, MANAGEMENT, PARENT, TEACHER, SIDEBAR_SECTIONS


_EXPECTED_SIDEBAR_KEYS = {
    MANAGEMENT: (
        "executive-dashboard",
        "learning-platform",
        "student-list",
        "academic-structure",
        "finance-dashboard",
        "documents",
        "system-settings",
        "transport-dashboard",
    ),
    TEACHER: ("teacher-home", "feedback"),
    PARENT: ("parent-home", "transport-dashboard"),
    DRIVER: ("transport-dashboard",),
    AUTHENTICATED: ("profile",),
}


def _read(root: Path, relative: str) -> tuple[str, list[AuditIssue]]:
    path = root / relative
    if not path.is_file():
        return "", [AuditIssue("single_entry_file_missing", f"ملف عقد المدخل الموحد مفقود: {relative}", relative)]
    try:
        return path.read_text(encoding="utf-8"), []
    except (OSError, UnicodeDecodeError) as exc:
        return "", [AuditIssue("single_entry_file_unreadable", f"تعذر قراءة {relative}: {exc}", relative)]


def _anchor_block_with_class(source: str, css_class: str) -> str:
    """Return the first explicit HTML anchor carrying ``css_class``.

    Class order and additional visual classes are intentionally ignored.  The
    contract protects the destination and the use of a real ``<a href>``; it
    must not couple the canonical-entry check to one historical CSS layout.
    """
    for match in re.finditer(r"<a\b(?P<attrs>[^>]*)>", source, flags=re.IGNORECASE | re.DOTALL):
        attrs = match.group("attrs")
        class_match = re.search(r"\bclass\s*=\s*([\"'])(?P<value>.*?)\1", attrs, flags=re.IGNORECASE | re.DOTALL)
        if not class_match or css_class not in class_match.group("value").split():
            continue
        href_match = re.search(r"\bhref\s*=\s*([\"']).*?\1", attrs, flags=re.IGNORECASE | re.DOTALL)
        if not href_match:
            continue
        end = source.find("</a>", match.end())
        return source[match.start() : (end + 4 if end >= 0 else match.end())]
    return ""


def _element_block_with_class(source: str, css_class: str) -> str:
    """Return a nav/section/div block by class for scoped route checks."""
    pattern = re.compile(r"<(nav|section|div)\b(?P<attrs>[^>]*)>", flags=re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(source):
        attrs = match.group("attrs")
        class_match = re.search(r"\bclass\s*=\s*([\"'])(?P<value>.*?)\1", attrs, flags=re.IGNORECASE | re.DOTALL)
        if not class_match or css_class not in class_match.group("value").split():
            continue
        tag = match.group(1)
        end = source.find(f"</{tag}>", match.end())
        return source[match.start() : (end + len(tag) + 3 if end >= 0 else match.end())]
    return ""


def _sidebar_keys(role: str) -> tuple[str, ...]:
    return tuple(
        key
        for section in SIDEBAR_SECTIONS.get(role, ())
        for key in section["items"]
    )


def audit_role_gateways() -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    for role, expected in _EXPECTED_SIDEBAR_KEYS.items():
        actual = _sidebar_keys(role)
        if actual != expected:
            issues.append(
                AuditIssue(
                    "role_gateway_drift",
                    f"مداخل الدور {role} تغيرت. المتوقع {expected} والموجود {actual}.",
                    "core/workflow_catalog.py",
                )
            )
    return issues


def audit_global_navigation_contract(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    issues: list[AuditIssue] = []
    context, read_issues = _read(root, "core/context_processors.py")
    issues.extend(read_issues)
    for token, message in (
        ("get_entry_operations_for_user", "البحث العام لا يستخدم قائمة مداخل الدور المعتمدة."),
        ('"opal_operation_catalog": entry_operations', "فهرس العمليات العام ما يزال يعرض إجراءات داخلية."),
        ('"opal_operation_groups": group_operations(entry_operations)', "مجموعات البحث العام لا تقتصر على البوابات."),
    ):
        if token not in context:
            issues.append(AuditIssue("global_entry_catalog", message, "core/context_processors.py"))

    workflow, read_issues = _read(root, "core/workflow_catalog.py")
    issues.extend(read_issues)
    if "def management_subnavigation_for_user" not in workflow or "return None" not in workflow:
        issues.append(AuditIssue("management_subnav_enabled", "صف الإجراءات الإداري الموازي لم يُعطّل.", "core/workflow_catalog.py"))

    topbar, read_issues = _read(root, "templates/includes/topbar.html")
    issues.extend(read_issues)
    if "core:operations_center" in topbar:
        issues.append(AuditIssue("topbar_operations_door", "دليل العمليات عاد كمدخل تشغيلي موازٍ في الشريط العلوي.", "templates/includes/topbar.html"))

    guide, read_issues = _read(root, "templates/core/operations_center.html")
    issues.extend(read_issues)
    for token in ('href="{{ operation.url }}"', 'href="{{ step.url }}"'):
        if token in guide:
            issues.append(AuditIssue("operations_guide_actionable", "دليل العمليات للقراءة فقط عاد يفتح إجراءً تشغيليًا.", "templates/core/operations_center.html"))
    return issues


def _template_route_locations(root: Path, route_name: str) -> set[str]:
    token_single = "{% url '" + route_name + "'"
    token_double = '{% url "' + route_name + '"'
    locations: set[str] = set()
    for template_root in (root / "templates", root / "dashboard" / "templates"):
        if not template_root.exists():
            continue
        for path in template_root.rglob("*.html"):
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if token_single in source or token_double in source:
                locations.add(path.relative_to(root).as_posix())
    return locations


def audit_canonical_visible_entries(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    issues: list[AuditIssue] = []
    allowed_locations = {
        "admissions:direct_registration": {"templates/students/student_list.html"},
        "admissions:fee_payment_create": {
            "templates/accounting/dashboard.html",
            # The form's own reset/search link remains inside the same workflow.
            "templates/admissions/fee_payment_form.html",
        },
        "core:system_updates": {"templates/core/system_settings.html"},
        "parent_portal:marks": {"templates/parent_portal/dashboard.html"},
        "teachers:portal_marks": {"templates/teachers/portal_workspace.html"},
        "teachers:teacher_create": {"templates/teachers/dashboard.html"},
        "academics:subject_list": {
            "templates/academics/academic_structure.html",
            "templates/academics/subject_form.html",
        },
        "timetable:dashboard": {
            "templates/academics/academic_structure.html",
            "templates/timetable/form.html",
        },
        "timetable:schedule_settings": {"templates/academics/academic_structure.html"},
        "timetable:absence_center": {
            "templates/academics/academic_structure.html",
            "templates/timetable/dashboard.html",
        },
        "exams:exam_list": {
            "templates/academics/academic_structure.html",
            "templates/exams/exam_form.html",
            "templates/exams/exam_list.html",
        },
        "documents:settings": {"templates/documents/document_list.html"},
        "documents:template_list": {
            "templates/documents/document_list.html",
            # The edit form's back link remains inside the same workflow.
            "templates/documents/template_form.html",
        },
        "students:student_update": {"templates/students/student_360.html"},
    }
    for route_name, allowed in allowed_locations.items():
        actual = _template_route_locations(root, route_name)
        if actual != allowed:
            issues.append(
                AuditIssue(
                    "canonical_entry_location",
                    f"المسار {route_name} يجب أن يظهر فقط في {sorted(allowed)}، والموجود {sorted(actual)}.",
                )
            )

    if _template_route_locations(root, "exams:exam_marks_bulk"):
        issues.append(AuditIssue("direct_bulk_marks_entry", "عاد رابط إدخال العلامات المباشر خارج مساحة المعلم الموحدة."))

    dashboard, read_issues = _read(root, "dashboard/templates/dashboard/home.html")
    issues.extend(read_issues)
    if "data-opal-card-link" in dashboard:
        issues.append(AuditIssue("executive_kpi_javascript_link", "بطاقات المؤشرات يجب أن تستخدم روابط HTML واضحة لا روابط JavaScript خفية.", "dashboard/templates/dashboard/home.html"))

    # Dashboard KPI cards may be clickable only when they land on the owning
    # canonical gateway (optionally at a fragment inside that gateway).  They
    # must never jump directly to a business operation and create a second door.
    expected_kpi_links = (
        ("opal-kpi-students", "students:student_list", "#student-list"),
        ("opal-kpi-teachers", "academics:academic_structure", "#teachers-operation"),
        ("opal-kpi-attendance", "academics:academic_structure", "#attendance-operation"),
        ("opal-kpi-collection", "accounting:dashboard", "#fee-summary"),
        ("opal-kpi-outstanding", "accounting:dashboard", "#outstanding-balances"),
        ("opal-kpi-success", "academics:academic_structure", "#exam-analysis-operation"),
    )
    for css_class, route_name, fragment in expected_kpi_links:
        segment = _anchor_block_with_class(dashboard, css_class)
        if not segment:
            issues.append(AuditIssue("executive_kpi_link_missing", f"بطاقة {css_class} ليست رابطًا واضحًا إلى بوابتها الرسمية.", "dashboard/templates/dashboard/home.html"))
            continue
        route_token = "{% url '" + route_name + "' %}"
        if route_token not in segment or fragment not in segment:
            issues.append(AuditIssue("executive_kpi_gateway_drift", f"بطاقة {css_class} يجب أن تقود إلى {route_name}{fragment} فقط.", "dashboard/templates/dashboard/home.html"))

    # Update 131.7 replaced the historical dashboard-card grid with a compact
    # semantic nav.  Audit the owning block by purpose, not by one CSS class.
    kpi_source = (
        _element_block_with_class(dashboard, "opal-manager-quick-row")
        or _element_block_with_class(dashboard, "opal-executive-kpis")
    )
    for forbidden_route in (
        "teachers:dashboard",
        "attendance_v2:dashboard",
        "exams:exam_list",
        "admissions:fee_payment_create",
    ):
        if forbidden_route in kpi_source:
            issues.append(AuditIssue("executive_kpi_direct_operation", f"بطاقات لوحة الإدارة تتجاوز البوابة الرسمية إلى {forbidden_route}.", "dashboard/templates/dashboard/home.html"))

    # The internal workflow service remains operational, but its executive-dashboard
    # shortcut was explicitly retired in Update 131.5 R3.  This is a visibility
    # decision, not a route or data deletion.
    hidden_dashboard_shortcuts = ("enterprise_ops:workflow_list",)
    for route_name in hidden_dashboard_shortcuts:
        visible_locations = _template_route_locations(root, route_name)
        if visible_locations:
            issues.append(
                AuditIssue(
                    "retired_dashboard_shortcut_visible",
                    f"الاختصار المتقاعد {route_name} يجب ألا يظهر في القوالب التنفيذية: {sorted(visible_locations)}.",
                    "dashboard/templates/dashboard/home.html",
                )
            )

    for required in (
        "enterprise_ops:feedback_list",
        "enterprise_ops:broadcast_list",
        "announcements:list",
    ):
        if required not in dashboard:
            issues.append(AuditIssue("management_communication_gateway", f"مدخل الإدارة {required} مفقود من لوحة الإدارة.", "dashboard/templates/dashboard/home.html"))

    parent_dashboard, read_issues = _read(root, "templates/parent_portal/dashboard.html")
    issues.extend(read_issues)
    for required in (
        "parent_portal:children",
        "parent_portal:marks",
        "parent_portal:homework",
        "parent_portal:fees",
        "parent_portal:attendance",
        "parent_portal:timetable",
        "parent_portal:documents",
        "parent_portal:teacher_evaluations",
        "parent_portal:announcements",
    ):
        if required not in parent_dashboard:
            issues.append(AuditIssue("parent_gateway_missing", f"مدخل ولي الأمر {required} مفقود من البوابة الرئيسية.", "templates/parent_portal/dashboard.html"))

    parent_detail, read_issues = _read(root, "templates/parent_portal/student_detail.html")
    issues.extend(read_issues)
    for forbidden in (
        "parent_portal:marks",
        "parent_portal:homework",
        "parent_portal:fees",
        "parent_portal:attendance",
        "parent_portal:timetable",
        "parent_portal:documents",
    ):
        if forbidden in parent_detail:
            issues.append(AuditIssue("parent_detail_parallel_entry", f"صفحة الابن تعيد مدخلًا موازيًا: {forbidden}.", "templates/parent_portal/student_detail.html"))

    teacher_dashboard, read_issues = _read(root, "templates/teachers/portal_dashboard.html")
    issues.extend(read_issues)
    for forbidden in ("teachers:portal_marks", "teachers:portal_homework", "exams:exam_marks_bulk"):
        if forbidden in teacher_dashboard:
            issues.append(AuditIssue("teacher_dashboard_parallel_entry", f"بوابة المعلم تعيد مدخلًا مباشرًا متجاوزًا لاختيار التكليف: {forbidden}.", "templates/teachers/portal_dashboard.html"))
    for mode in ("mode=subjects", "mode=students", "mode=marks", "mode=homework"):
        if mode not in teacher_dashboard:
            issues.append(AuditIssue("teacher_workspace_gateway", f"بوابة المعلم تفتقد المسار الموحد {mode}.", "templates/teachers/portal_dashboard.html"))
    return issues


def run_single_entry_contract_audit(root: Path | None = None) -> dict:
    root = (root or project_root()).resolve()
    checks = {
        "role_gateways": audit_role_gateways(),
        "global_navigation": audit_global_navigation_contract(root=root),
        "canonical_visible_entries": audit_canonical_visible_entries(root=root),
    }
    issues = [issue for group in checks.values() for issue in group]
    return {
        "ok": not issues,
        "checks": {name: not group for name, group in checks.items()},
        "issue_count": len(issues),
        "issues": [issue.as_dict() for issue in issues],
    }
