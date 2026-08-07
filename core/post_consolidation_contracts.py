"""Post-consolidation performance and stability contracts for OPAL Update 131.1.

These checks inspect source contracts only and never touch school data.  They
protect the fixes that keep ordinary page rendering read-only and prevent the
full live-management/TPI engines from running on every request.
"""

from __future__ import annotations

import re
from pathlib import Path

from .final_reengineering_audit import AuditIssue, project_root


_WRITE_MARKERS = (
    ".save(",
    ".create(",
    ".update(",
    ".delete(",
    "get_or_create(",
    "update_or_create(",
    "bulk_create(",
    "bulk_update(",
)


def _read(root: Path, relative: str) -> str:
    path = root / relative
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def audit_global_context_processors_are_read_only(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    issues: list[AuditIssue] = []

    notification_path = "enterprise_ops/context_processors.py"
    notification_source = _read(root, notification_path)
    if "sync_attendance_registers" in notification_source:
        issues.append(
            AuditIssue(
                "global_attendance_sync",
                "لا يجوز تشغيل مزامنة سجلات الحضور من معالج سياق يعمل على كل صفحة.",
                notification_path,
            )
        )
    for marker in _WRITE_MARKERS:
        if marker in notification_source:
            issues.append(
                AuditIssue(
                    "context_processor_write",
                    f"معالج الإشعارات العام يحتوي عملية كتابة محتملة: {marker}",
                    notification_path,
                )
            )

    timetable_path = "timetable/context_processors.py"
    timetable_source = _read(root, timetable_path)
    if "management_live_status" in timetable_source:
        issues.append(
            AuditIssue(
                "heavy_global_live_status",
                "معالج الشريط العلوي لا يجوز أن يبني حالة الإدارة التفصيلية على كل صفحة.",
                timetable_path,
            )
        )
    if "school_live_status" not in timetable_source:
        issues.append(
            AuditIssue(
                "compact_live_status_missing",
                "حالة الشريط العلوي للإدارة يجب أن تستخدم حالة المدرسة المختصرة.",
                timetable_path,
            )
        )
    return issues


def audit_tpi_page_reads_are_explicit(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    issues: list[AuditIssue] = []
    views_path = "teachers/views.py"
    views = _read(root, views_path)

    dashboard_match = re.search(
        r"def dashboard\(request\):(.*?)(?=\n@management_required\n(?:def|@)|\n@teacher_required\n(?:def|@))",
        views,
        flags=re.S,
    )
    dashboard = dashboard_match.group(1) if dashboard_match else ""
    if "management_tpi_snapshot_context" not in dashboard:
        issues.append(
            AuditIssue(
                "management_tpi_read_path",
                "فتح لوحة المعلمين يجب أن يقرأ لقطات TPI بدل إعادة حساب المدرسة.",
                views_path,
            )
        )
    if 'request.method == "POST"' not in dashboard or 'action") == "refresh_tpi"' not in dashboard:
        issues.append(
            AuditIssue(
                "explicit_tpi_refresh_missing",
                "تحديث TPI الكامل يجب أن يكون إجراء POST صريحًا داخل البوابة الحالية.",
                views_path,
            )
        )

    portal_match = re.search(
        r"def portal_dashboard\(request\):(.*?)(?=\n@teacher_required\n(?:def|@)|\n@management_required\n(?:def|@))",
        views,
        flags=re.S,
    )
    portal = portal_match.group(1) if portal_match else ""
    if "teacher_tpi_snapshot_context" not in portal or "teacher_tpi_context(" in portal:
        issues.append(
            AuditIssue(
                "teacher_portal_tpi_write_path",
                "بوابة المعلم يجب أن تقرأ لقطة TPI فقط ولا تعيد حساب المدرسة عند كل دخول.",
                views_path,
            )
        )

    tpi_path = "teachers/tpi.py"
    tpi_source = _read(root, tpi_path)
    for function_name in ("management_tpi_snapshot_context", "teacher_tpi_snapshot_context"):
        if f"def {function_name}" not in tpi_source:
            issues.append(
                AuditIssue(
                    "tpi_snapshot_reader_missing",
                    f"قارئ TPI غير الكتابي مفقود: {function_name}",
                    tpi_path,
                )
            )
    return issues


def audit_teacher_management_scope(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    path = "teachers/views.py"
    source = _read(root, path)
    issues: list[AuditIssue] = []
    if "school = request_school(request)" not in source:
        issues.append(
            AuditIssue(
                "teacher_school_scope_missing",
                "شاشات إدارة المعلمين يجب أن تستخدم المدرسة النشطة من سياق الطلب.",
                path,
            )
        )
    if "Teacher.objects.filter(school=school)" not in source:
        issues.append(
            AuditIssue(
                "teacher_queryset_unscoped",
                "قائمة المعلمين يجب أن تكون مقيدة بالمدرسة النشطة.",
                path,
            )
        )
    if "teacher__school=school" not in source:
        issues.append(
            AuditIssue(
                "teacher_assignment_scope_missing",
                "تكليفات المعلمين المعروضة يجب أن تكون مقيدة بالمدرسة النشطة.",
                path,
            )
        )
    return issues


def run_post_consolidation_stability_audit(root: Path | None = None) -> dict:
    checks = {
        "global_context_read_only": audit_global_context_processors_are_read_only(root=root),
        "tpi_page_read_paths": audit_tpi_page_reads_are_explicit(root=root),
        "teacher_management_scope": audit_teacher_management_scope(root=root),
    }
    issues = [issue for group in checks.values() for issue in group]
    return {
        "ok": not issues,
        "checks": {name: not group for name, group in checks.items()},
        "issue_count": len(issues),
        "issues": [issue.as_dict() for issue in issues],
    }
