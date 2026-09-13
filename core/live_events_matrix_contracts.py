"""Source contracts for OPAL Update 131.4 live events matrix and time reliability."""

from __future__ import annotations

from pathlib import Path

from .final_reengineering_audit import AuditIssue, project_root


def _read(root: Path, relative: str) -> str:
    path = root / relative
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def audit_live_events_matrix(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    issues: list[AuditIssue] = []
    template_path = "dashboard/templates/dashboard/home.html"
    template = _read(root, template_path)
    live_path = "timetable/live_services.py"
    live = _read(root, live_path)
    css_path = "static/css/opal_theme_system.css"
    css = _read(root, css_path)

    for token, message in (
        ("opal_live_schedule.grade_columns", "مصفوفة الأحداث الأفقية لا تستخدم أعمدة الصفوف والشعب."),
        ('colspan="{{ column.section_count }}"', "خلية الصف لا تمتد فوق عدد شعبه."),
        ("الحدث الجاري", "صف الحدث الجاري غير موجود في المصفوفة."),
        ("item.short_name", "اسم الشعبة المختصر غير معروض داخل صف الشعب."),
        ('data-live-seconds="{{ opal_live_schedule.seconds_remaining', "حد الانتقال الزمني غير منشور لتحديث الحالة تلقائيًا."),
        ('data-opal-official-clock="time"', "وقت المدرسة الرسمي غير ظاهر بجانب الحالة الحية."),
    ):
        if token not in template:
            issues.append(AuditIssue("live_events_matrix_template_incomplete", message, template_path))

    for token, message in (
        ('"grade_columns": grade_columns', "خدمة الحالة الحية لا تعيد بنية الصف/الشعبة الأفقية."),
        ('"short_name": short_name or section.name', "الخدمة لا تعيد اسم الشعبة المختصر."),
        ('"state": "no_schedule"', "اليوم بلا جدول لا يتميز عن انتهاء الدوام."),
        ('"state"] = "not_started" if before_first_event else "between"', "بداية الدوام لا تتميز عن الفراغ بين حدثين."),
        ('teacher_state_active = base.get("state") in {"active", "between"}', "قوائم المعلمين قد تظهر قبل بدء الدوام أو في يوم بلا جدول."),
        ("Generic\n    # time-slot definitions must not invent a school day", "الحالة الحية ما زالت قد تُنشئ دوامًا وهميًا من تعريفات الحصص العامة."),
    ):
        if token not in live:
            issues.append(AuditIssue("live_events_matrix_service_incomplete", message, live_path))

    for token, message in (
        ("OPAL Update 131.4: live grade/section event matrix", "أنماط المصفوفة الحية غير منشورة."),
        (".opal-live-events-matrix .opal-live-axis-cell", "عمود عناوين الصف/الشعبة/الحدث غير مثبت."),
        ("position:sticky", "التثبيت البصري للعمود الرأسي غير موجود."),
        ("overflow-x:auto", "المصفوفة لا تسمح بالسحب الأفقي على الهاتف."),
    ):
        if token not in css:
            issues.append(AuditIssue("live_events_matrix_css_incomplete", message, css_path))
    return issues


def audit_official_time_refresh(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    issues: list[AuditIssue] = []
    js_path = "static/js/opal_erp.js"
    js = _read(root, js_path)
    for token, message in (
        ("function officialNow()", "الساعة لا تزال بحاجة إلى مرجع وقت الخادم."),
        ('[data-opal-official-clock="time"]', "ساعة صندوق الأحداث لا تتحدث من المرجع الرسمي."),
        ("function installLiveBoundaryRefresh()", "اللوحة لا تعيد تحميل الحالة عند حد الحصة أو الاستراحة."),
        ("nearestBoundary + 1", "توقيت التحديث التلقائي عند الحد التالي غير مضبوط."),
    ):
        if token not in js:
            issues.append(AuditIssue("official_time_refresh_incomplete", message, js_path))
    return issues


def run_live_events_matrix_audit(root: Path | None = None) -> dict:
    checks = {
        "live_events_matrix": audit_live_events_matrix(root=root),
        "official_time_refresh": audit_official_time_refresh(root=root),
    }
    issues = [issue for group in checks.values() for issue in group]
    return {
        "ok": not issues,
        "checks": {name: not group for name, group in checks.items()},
        "issue_count": len(issues),
        "issues": [issue.as_dict() for issue in issues],
    }
