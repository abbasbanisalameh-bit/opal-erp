"""Django system checks for OPAL's canonical runtime shell."""

from pathlib import Path

from django.conf import settings
from django.core.checks import Error, Tags, register

from .runtime_contracts import run_runtime_stability_audit
from .critical_workflow_contracts import run_critical_workflow_contract_audit
from .single_entry_contracts import run_single_entry_contract_audit
from .school_finance_language_contracts import run_school_finance_language_audit
from .smart_timetable_contracts import run_smart_timetable_contract_audit
from .post_consolidation_contracts import run_post_consolidation_stability_audit
from .live_operations_contracts import run_live_operations_repair_audit
from .capacity_timezone_contracts import run_capacity_timezone_audit
from .live_events_matrix_contracts import run_live_events_matrix_audit
from .fixed_dashboard_contracts import run_fixed_dashboard_audit
from .subject_ui_contracts import run_subject_ui_audit
from .dashboard_truth_contracts import run_dashboard_truth_audit


def _horizontal_timetable_matrix_issues():
    """Verify that the production matrix and mobile containment were deployed."""
    required_templates = (
        "templates/timetable/dashboard.html",
        "templates/timetable/print.html",
        "templates/teachers/portal_timetable.html",
        "templates/teachers/portal_dashboard.html",
        "templates/teachers/teacher_detail.html",
        "templates/parent_portal/timetable.html",
        "templates/students/student_360.html",
    )
    root = Path(settings.BASE_DIR)
    issues = []
    for relative in required_templates:
        path = root / relative
        if not path.is_file():
            issues.append({
                "code": "TIMETABLE_MATRIX_TEMPLATE_MISSING",
                "message": "قالب مصفوفة الجدول الأفقي غير موجود.",
                "path": relative,
            })
            continue
        source = path.read_text(encoding="utf-8")
        missing = [
            marker
            for marker in ("opal-timetable-grid", "اليوم / الحصة", "opal-keep-grid")
            if marker not in source
        ]
        if missing:
            issues.append({
                "code": "TIMETABLE_MATRIX_NOT_DEPLOYED",
                "message": "لم يُنشر عرض الجدول الأفقي فعليًا؛ العلامات المفقودة: " + "، ".join(missing),
                "path": relative,
            })

    current_lesson_templates = (
        "templates/timetable/dashboard.html",
        "templates/teachers/portal_timetable.html",
        "templates/teachers/portal_dashboard.html",
        "templates/teachers/teacher_detail.html",
        "templates/parent_portal/timetable.html",
        "templates/students/student_360.html",
    )
    for relative in current_lesson_templates:
        path = root / relative
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        if "is_current_lesson" not in source or "opal-current-lesson-badge" not in source:
            issues.append({
                "code": "CURRENT_LESSON_STATE_NOT_DEPLOYED",
                "message": "تمييز الحصة الجارية غير منشور في عرض الجدول الرسمي.",
                "path": relative,
            })

    css_path = root / "static/css/opal_erp.css"
    css_source = css_path.read_text(encoding="utf-8") if css_path.is_file() else ""
    for marker in (
        "OPAL Update 130: production timetable state and mobile containment",
        "OPAL Update 131: consolidated timetable states and print contract",
        ".opal-timetable-entry.is-current",
        "width: min(86dvw, 330px) !important",
    ):
        if marker not in css_source:
            issues.append({
                "code": "MOBILE_CONTAINMENT_NOT_DEPLOYED",
                "message": "إصلاح احتواء الصفحة والقائمة الجانبية على الهاتف غير مكتمل.",
                "path": "static/css/opal_erp.css",
            })
            break

    version_file = root / "OPAL_VERSION.txt"
    version = version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else ""
    if version != "131.7":
        issues.append({
            "code": "TIMETABLE_RELEASE_IDENTITY_MISMATCH",
            "message": f"هوية الكود الفعلية يجب أن تكون 131.7 وليست {version or 'غير محددة'}.",
            "path": "OPAL_VERSION.txt",
        })
    return issues


@register(Tags.compatibility)
def opal_runtime_stability_checks(app_configs, **kwargs):
    del app_configs, kwargs
    runtime = run_runtime_stability_audit()
    critical = run_critical_workflow_contract_audit()
    single_entry = run_single_entry_contract_audit()
    finance_language = run_school_finance_language_audit()
    smart_timetable = run_smart_timetable_contract_audit()
    post_consolidation = run_post_consolidation_stability_audit()
    live_operations = run_live_operations_repair_audit()
    capacity_timezone = run_capacity_timezone_audit()
    live_events_matrix = run_live_events_matrix_audit()
    fixed_dashboard = run_fixed_dashboard_audit()
    subject_ui = run_subject_ui_audit()
    dashboard_truth = run_dashboard_truth_audit()
    horizontal_matrix = _horizontal_timetable_matrix_issues()
    errors = [
        Error(
            f"[{issue['code']}] {issue['message']}",
            hint=issue.get("path") or None,
            id="opal.E122",
        )
        for issue in runtime["issues"]
    ]
    errors.extend(
        Error(
            f"[{issue['code']}] {issue['message']}",
            hint=issue.get("path") or None,
            id="opal.E124",
        )
        for issue in critical["issues"]
    )
    errors.extend(
        Error(
            f"[{issue['code']}] {issue['message']}",
            hint=issue.get("path") or None,
            id="opal.E125",
        )
        for issue in single_entry["issues"]
    )
    errors.extend(
        Error(
            f"[{issue['code']}] {issue['message']}",
            hint=issue.get("path") or None,
            id="opal.E126",
        )
        for issue in finance_language["issues"]
    )
    errors.extend(
        Error(
            f"[{issue['code']}] {issue['message']}",
            hint=issue.get("path") or None,
            id="opal.E127",
        )
        for issue in smart_timetable["issues"]
    )
    errors.extend(
        Error(
            f"[{issue['code']}] {issue['message']}",
            hint=issue.get("path") or None,
            id="opal.E131",
        )
        for issue in post_consolidation["issues"]
    )
    errors.extend(
        Error(
            f"[{issue['code']}] {issue['message']}",
            hint=issue.get("path") or None,
            id="opal.E132",
        )
        for issue in live_operations["issues"]
    )
    errors.extend(
        Error(
            f"[{issue['code']}] {issue['message']}",
            hint=issue.get("path") or None,
            id="opal.E133",
        )
        for issue in capacity_timezone["issues"]
    )
    errors.extend(
        Error(
            f"[{issue['code']}] {issue['message']}",
            hint=issue.get("path") or None,
            id="opal.E134",
        )
        for issue in live_events_matrix["issues"]
    )
    errors.extend(
        Error(
            f"[{issue['code']}] {issue['message']}",
            hint=issue.get("path") or None,
            id="opal.E137",
        )
        for issue in fixed_dashboard["issues"]
    )
    errors.extend(
        Error(
            f"[{issue['code']}] {issue['message']}",
            hint=issue.get("path") or None,
            id="opal.E136",
        )
        for issue in subject_ui["issues"]
    )
    errors.extend(
        Error(
            f"[{issue['code']}] {issue['message']}",
            hint=issue.get("path") or None,
            id="opal.E138",
        )
        for issue in dashboard_truth["issues"]
    )
    errors.extend(
        Error(
            f"[{issue['code']}] {issue['message']}",
            hint=issue.get("path") or None,
            id="opal.E130",
        )
        for issue in horizontal_matrix
    )
    return errors
