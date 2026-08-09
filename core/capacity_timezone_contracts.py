"""Source contracts for OPAL Update 131.3 capacity data and school time."""

from __future__ import annotations

from pathlib import Path

from .final_reengineering_audit import AuditIssue, project_root


def _read(root: Path, relative: str) -> str:
    path = root / relative
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def audit_capacity_seed(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    issues: list[AuditIssue] = []
    path = "core/system_data.py"
    source = _read(root, path)
    required = (
        "DEMO_STUDENT_COUNT = 500",
        "DEMO_GUARDIAN_COUNT = 200",
        "DEMO_TEACHER_COUNT = 30",
        "DEMO_TEACHER_WEEKLY_LOAD = 30",
        "DEMO_TEACHER_DAILY_TARGET = 6",
        '("اللغة العربية", 5)',
        '("الرياضيات", 5)',
        '("العلوم", 5)',
        '("التربية الرياضية", 2)',
        '("التربية المهنية", 2)',
        'enforce_daily_teaching_target=True',
        'teacher.daily_free_periods = 1',
    )
    missing = [token for token in required if token not in source]
    if missing:
        issues.append(AuditIssue(
            "capacity_seed_contract_missing",
            "زر إدخال البيانات لا يطابق عقد R29: 500 طالب/200 ولي أمر/30 معلم ونصاب 30 حصة وخطة المواد المترابطة.",
            path,
        ))
    return issues




_CAPACITY_SUBJECT_IDENTITIES = (
    "اللغة العربية", "الرياضيات", "التربية الرياضية", "اللغة الإنجليزية",
    "التربية المهنية", "التربية الإسلامية", "الحاسوب", "التربية الفنية",
    "الثقافة المالية", "العلوم", "الاجتماعيات", "التاريخ", "الجغرافيا",
    "التربية الوطنية", "الفيزياء", "الكيمياء", "الأحياء", "علوم الأرض",
)


def audit_capacity_subject_palette(root: Path | None = None) -> list[AuditIssue]:
    """Prove that the full acceptance-plan identities can be coloured safely."""
    from django.core.exceptions import ValidationError
    from academics.subject_identity import (
        colour_distance, default_subject_colour, normalize_subject_key,
    )

    issues: list[AuditIssue] = []
    used: list[str] = []
    try:
        for name in _CAPACITY_SUBJECT_IDENTITIES:
            colour = default_subject_colour(normalize_subject_key(name), used)
            used.append(colour)
    except ValidationError as exc:
        issues.append(AuditIssue(
            "capacity_subject_palette_exhausted",
            f"لوحة ألوان المواد لا تستوعب جميع مواد بيانات السعة: {exc}",
            "academics/subject_identity.py",
        ))
        return issues

    if len(set(used)) != len(_CAPACITY_SUBJECT_IDENTITIES):
        issues.append(AuditIssue(
            "capacity_subject_palette_duplicate",
            "لوحة ألوان بيانات السعة أعادت لونًا مكررًا لهويتين مختلفتين.",
            "academics/subject_identity.py",
        ))
        return issues

    minimum = min(
        colour_distance(first, second)
        for index, first in enumerate(used)
        for second in used[index + 1:]
    )
    if minimum < 45:
        issues.append(AuditIssue(
            "capacity_subject_palette_distance",
            f"أقل تباعد بين ألوان مواد بيانات السعة هو {minimum:.2f} ويجب ألا يقل عن 45.",
            "academics/subject_identity.py",
        ))
    return issues


def audit_authoritative_school_time(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    issues: list[AuditIssue] = []
    preferences_path = "config/site_preferences.py"
    context_path = "core/context_processors.py"
    base_path = "templates/base/base.html"
    js_path = "static/js/opal_erp.js"
    preferences = _read(root, preferences_path)
    context = _read(root, context_path)
    base = _read(root, base_path)
    js = _read(root, js_path)

    if "OPAL_TIME_ZONE" not in preferences or "Asia/Amman" not in preferences:
        issues.append(AuditIssue(
            "school_timezone_default_missing",
            "المنطقة الزمنية الافتراضية للمدرسة يجب أن تكون Asia/Amman وقابلة للضبط بيئيًا.",
            preferences_path,
        ))
    if '"opal_server_now": timezone.now()' not in context:
        issues.append(AuditIssue(
            "server_clock_context_missing",
            "الواجهة تحتاج وقت الخادم المرجعي حتى لا تعتمد على ساعة جهاز المستخدم.",
            context_path,
        ))
    if "data-opal-time-zone" not in base or "data-opal-server-now" not in base:
        issues.append(AuditIssue(
            "server_clock_html_missing",
            "القالب العام لا يمرر منطقة المدرسة ووقت الخادم إلى ساعة الواجهة.",
            base_path,
        ))
    if "opalServerStart" not in js or "timeZone: opalClockZone" not in js:
        issues.append(AuditIssue(
            "authoritative_clock_script_missing",
            "ساعة الواجهة لا تستخدم وقت الخادم والمنطقة الزمنية الرسمية للمدرسة.",
            js_path,
        ))
    return issues


def run_capacity_timezone_audit(root: Path | None = None) -> dict:
    checks = {
        "capacity_seed": audit_capacity_seed(root=root),
        "capacity_subject_palette": audit_capacity_subject_palette(root=root),
        "authoritative_school_time": audit_authoritative_school_time(root=root),
    }
    issues = [issue for group in checks.values() for issue in group]
    return {
        "ok": not issues,
        "checks": {name: not group for name, group in checks.items()},
        "issue_count": len(issues),
        "issues": [issue.as_dict() for issue in issues],
    }
