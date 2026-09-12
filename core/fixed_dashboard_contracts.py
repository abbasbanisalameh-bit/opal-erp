"""Contracts for OPAL Update 131.7 fixed manager dashboard."""

from pathlib import Path

from django.conf import settings


def _read(root: Path, relative: str) -> str:
    path = root / relative
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def run_fixed_dashboard_audit() -> dict[str, object]:
    root = Path(settings.BASE_DIR)
    issues: list[dict[str, str]] = []
    template = _read(root, "dashboard/templates/dashboard/home.html")
    views = _read(root, "dashboard/views.py")
    workflow = _read(root, "dashboard/workflow.py")
    css = _read(root, "static/css/opal_theme_system.css")

    required = {
        "dashboard/templates/dashboard/home.html": (
            "opal-fixed-manager-dashboard",
            "opal-manager-quick-row",
            "opal-teacher-performance-row",
            "opal-top-students-panel",
            "opal-satisfaction-fixed",
            "opal-actions-fixed-row",
            "آخر 10 طلاب مسجلين وصفوفهم",
            "الأحداث الجارية لكل صف وشعبة",
        ),
        "dashboard/views.py": (
            "@require_GET",
            "fixed canonical manager dashboard",
            "build_dashboard_context(request)",
        ),
        "dashboard/workflow.py": (
            'latest_enrollments = Enrollment.objects.filter(',
            "top_students_matrix",
            'row.get("rank") == 1',
        ),
        "static/css/opal_theme_system.css": (
            "OPAL Update 131.7 — fixed crystal manager dashboard",
            ".opal-manager-quick-row",
            "grid-template-columns:repeat(6,minmax(0,1fr))",
            "border:1px dashed rgba(216,173,79",
            ".opal-fixed-pair",
            ".opal-latest-students-grid",
        ),
    }
    for relative, markers in required.items():
        source = _read(root, relative)
        if not source:
            issues.append({"code": "FIXED_DASHBOARD_FILE_MISSING", "message": "ملف لوحة المدير الثابتة غير موجود.", "path": relative})
            continue
        missing = [marker for marker in markers if marker not in source]
        if missing:
            issues.append({"code": "FIXED_DASHBOARD_CONTRACT_MISSING", "message": "تنفيذ لوحة المدير الثابتة غير مكتمل: " + "، ".join(missing), "path": relative})

    retired = (
        "opal-dashboard-layout-form",
        "opal-dashboard-layout-data",
        "data-opal-layout-edit",
        "save_dashboard_layout",
        "reset_dashboard_layout",
        "user_dashboard_layout",
    )
    combined = template + "\n" + views
    if any(marker in combined for marker in retired):
        issues.append({"code": "DASHBOARD_CUSTOMIZER_STILL_ACTIVE", "message": "يجب حذف أداة تخصيص لوحة المدير ومسارات حفظها من التشغيل نهائيًا.", "path": "dashboard/templates/dashboard/home.html"})

    if (root / "static/js/opal_dashboard_layout.js").exists() or (root / "dashboard/layout.py").exists():
        issues.append({"code": "DASHBOARD_CUSTOMIZER_FILES_REMAIN", "message": "ملفات أداة التخصيص القديمة ما زالت ضمن الحزمة.", "path": "dashboard/"})

    order_markers = (
        "opal-manager-quick-row",
        "opal-teacher-performance-row",
        "opal-top-students-panel",
        "opal-satisfaction-fixed",
        "مصادر التقييم وملخص المتابعة",
        "الإيرادات والمتأخرون عن السداد",
        "المعلمون المشغولون والمتفرغون",
        "opal-live-operation-title",
        "opal-actions-fixed-row",
        "غياب الطلبة والمعلمين اليوم",
        "opal-latest-students-title",
    )
    positions = [template.find(marker) for marker in order_markers]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        issues.append({"code": "FIXED_DASHBOARD_ORDER_MISMATCH", "message": "ترتيب عناصر لوحة المدير لا يطابق التسلسل التشغيلي المعتمد.", "path": "dashboard/templates/dashboard/home.html"})

    return {"ok": not issues, "issues": issues}
