"""Contracts that keep manager-dashboard values tied to authoritative records."""

from pathlib import Path

from django.conf import settings


def _read(root: Path, relative: str) -> str:
    path = root / relative
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def run_dashboard_truth_audit() -> dict[str, object]:
    root = Path(settings.BASE_DIR)
    issues: list[dict[str, str]] = []
    workflow = _read(root, "dashboard/workflow.py")
    template = _read(root, "dashboard/templates/dashboard/home.html")
    satisfaction = _read(root, "enterprise_ops/services.py")
    evaluations = _read(root, "parent_portal/evaluation_services.py")
    command = _read(root, "dashboard/management/commands/audit_dashboard_truth.py")

    required = {
        "dashboard/workflow.py": (
            "build_school_attendance_period_snapshot(period_start, today, school=school, academic_year=academic_year)",
            "Teacher.objects.filter(school=school, is_active=True)",
            "StudentInvoice.objects.filter(academic_year=academic_year)",
            "StudentMark.objects.filter(",
            "exam__academic_year=academic_year",
            "finance_data_available",
            "academic_data_available",
            "latest_enrollments = Enrollment.objects.filter(",
            "no_recent_payment_total",
            'monthly_teacher_evaluation_snapshot(today=today, school=school)',
            'feedback_satisfaction_snapshot(today=today, school=school)',
        ),
        "enterprise_ops/services.py": (
            "feedback_total = participation_qs.count()",
            "both_positive / paired_total",
            "feedback_data_available",
            "school=school",
        ),
        "parent_portal/evaluation_services.py": (
            "def monthly_teacher_evaluation_snapshot(today=None, school=None):",
            "teacher__school=school",
        ),
        "dashboard/templates/dashboard/home.html": (
            "بيانات مباشرة من السجلات المعتمدة",
            "لا يوجد سجل حضور معتمد",
            "لم تُعتمد سجلات حضور الشعب اليوم",
            "لا توجد علامات رسمية",
            "لا توجد رسوم للعام الحالي",
        ),
        "dashboard/management/commands/audit_dashboard_truth.py": (
            "finance_remaining",
            "satisfaction_participations_direct",
            "latest_students",
            "live_grade_event_matrix",
            "monthly_income_values",
        ),
    }
    sources = {
        "dashboard/workflow.py": workflow,
        "enterprise_ops/services.py": satisfaction,
        "parent_portal/evaluation_services.py": evaluations,
        "dashboard/templates/dashboard/home.html": template,
        "dashboard/management/commands/audit_dashboard_truth.py": command,
    }
    for relative, markers in required.items():
        source = sources[relative]
        if not source:
            issues.append({"code": "DASHBOARD_TRUTH_FILE_MISSING", "message": "ملف تدقيق حقيقة بيانات اللوحة مفقود.", "path": relative})
            continue
        missing = [marker for marker in markers if marker not in source]
        if missing:
            issues.append({
                "code": "DASHBOARD_TRUTH_CONTRACT_MISSING",
                "message": "تنفيذ ربط مؤشرات اللوحة بمصادرها غير مكتمل: " + "، ".join(missing),
                "path": relative,
            })

    forbidden = (
        "Student.objects.aggregate(",
        "Teacher.objects.filter(is_active=True).count()",
        "Section.objects.count()",
        'feedback_satisfaction_snapshot(today=today)',
        'monthly_teacher_evaluation_snapshot(today=today)',
    )
    found = [marker for marker in forbidden if marker in workflow]
    if found:
        issues.append({
            "code": "DASHBOARD_UNSCOPED_QUERY_REMAINS",
            "message": "لا يجوز خلط سجلات خارج المدرسة أو العام الحالي في لوحة المدير: " + "، ".join(found),
            "path": "dashboard/workflow.py",
        })

    fake_chart_markers = (
        ':["لا توجد بيانات"]',
        ':["لا توجد تقييمات"]',
        ":[0]",
    )
    fake_found = [marker for marker in fake_chart_markers if marker in template]
    if fake_found:
        issues.append({
            "code": "DASHBOARD_SYNTHETIC_CHART_FALLBACK",
            "message": "يجب عرض حالة لا توجد بيانات بدل إنشاء قيمة صفرية مصطنعة للرسم.",
            "path": "dashboard/templates/dashboard/home.html",
        })

    return {"ok": not issues, "issues": issues}
