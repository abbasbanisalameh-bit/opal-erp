"""Live-operations repair contracts for OPAL Update 131.2.

These source-only checks protect the director live dashboard and prevent a
single day's teacher exception from leaking into every weekday row.
"""

from __future__ import annotations

from pathlib import Path

from .final_reengineering_audit import AuditIssue, project_root


def _read(root: Path, relative: str) -> str:
    path = root / relative
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def audit_weekly_teacher_state_scope(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    issues: list[AuditIssue] = []
    attendance_path = "timetable/attendance_services.py"
    attendance = _read(root, attendance_path)
    workflow_path = "timetable/workflow.py"
    workflow = _read(root, workflow_path)

    if "def decorate_weekly_entries_with_current_status" not in attendance:
        issues.append(AuditIssue(
            "weekly_status_decorator_missing",
            "مصفوفة الجدول الأسبوعي تحتاج مزينًا يطبق استثناء الدوام على صف اليوم فقط.",
            attendance_path,
        ))
    if "item.day == current_day_code" not in attendance or "neutral_state" not in attendance:
        issues.append(AuditIssue(
            "weekly_status_neutral_rows_missing",
            "صفوف الأيام غير الحالية يجب أن تبقى بحالة محايدة ولا ترث استثناء اليوم.",
            attendance_path,
        ))
    if "decorate_weekly_entries_with_current_status(" not in workflow:
        issues.append(AuditIssue(
            "weekly_matrix_wrong_decorator",
            "منشئ المصفوفة الأسبوعية لا يستخدم نطاق حالة الدوام الخاص بيوم اليوم.",
            workflow_path,
        ))
    return issues


def audit_management_live_dashboard(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    issues: list[AuditIssue] = []
    dashboard_path = "dashboard/workflow.py"
    dashboard = _read(root, dashboard_path)
    template_path = "dashboard/templates/dashboard/home.html"
    template = _read(root, template_path)
    live_path = "timetable/live_services.py"
    live = _read(root, live_path)

    if '"opal_live_schedule": management_live_status(school)' not in dashboard:
        issues.append(AuditIssue(
            "management_live_context_missing",
            "لوحة المدير يجب أن تستدعي حالة التشغيل التفصيلية داخل صفحة اللوحة فقط.",
            dashboard_path,
        ))
    for token, message in (
        ("opal_live_schedule.grade_columns", "صندوق الحدث الجاري لكل صف غير منشور في لوحة المدير."),
        ("opal_live_schedule.busy_rows", "قائمة المعلمين المشغولين لا تستخدم المعلم الفعلي أو البديل."),
        ("opal_live_schedule.free_teachers", "قائمة المعلمين المتفرغين غير منشورة في لوحة المدير."),
    ):
        if token not in template:
            issues.append(AuditIssue("management_live_template_missing", message, template_path))

    for token, message in (
        ('"busy_rows": busy_rows', "خدمة الحالة الحية لا تعيد صفوف المعلمين المشغولين الفعلية."),
        ('entry.teacher_state_code == "available"', "المعلم غير المتاح قد يُصنف خطأً بوصفه مشغولًا."),
        ('current_event.get("kind") != "class"', "الاستراحة أو الحدث الصريح لا يتقدم على الحصة عند التداخل."),
        ('"teacher_state_active": teacher_state_active', "حالة الإشغال خارج الدوام غير مضبوطة."),
    ):
        if token not in live:
            issues.append(AuditIssue("management_live_service_incomplete", message, live_path))
    return issues


def run_live_operations_repair_audit(root: Path | None = None) -> dict:
    checks = {
        "weekly_teacher_state_scope": audit_weekly_teacher_state_scope(root=root),
        "management_live_dashboard": audit_management_live_dashboard(root=root),
    }
    issues = [issue for group in checks.values() for issue in group]
    return {
        "ok": not issues,
        "checks": {name: not group for name, group in checks.items()},
        "issue_count": len(issues),
        "issues": [issue.as_dict() for issue in issues],
    }
