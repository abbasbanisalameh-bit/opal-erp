#!/usr/bin/env python3
"""Verify that an OPAL Update 131.7 ZIP is complete and contains code only."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import PurePosixPath, Path

EXPECTED_VERSION = "131.7"
MIN_PACKAGE_REVISION = 28
REQUIRED = {
    "manage.py",
    "requirements.txt",
    "OPAL_VERSION.txt",
    "OPAL_RELEASE_NAME.txt",
    "OPAL_UPDATE_MANIFEST.json",
    "academics/migrations/0016_annual_subject_plan_stage.py",
    "academics/migrations/0017_finalize_annual_subject_plan.py",
    "academics/migrations/0018_alter_subject_canonical_key_alter_subject_grade.py",
    "teachers/migrations/0014_subject_plan_single_source.py",
    "timetable/migrations/0008_subject_plan_protection.py",
    "curriculum/migrations/0003_remove_parallel_curriculum.py",
    "tools/validate_opal_update_131_source.py",
    "tools/opal_update_131_preflight.py",
    "core/capacity_timezone_contracts.py",
    "core/test_update131_3_capacity_timezone_contract.py",
    "core/live_events_matrix_contracts.py",
    "core/test_update131_4_live_events_matrix_contract.py",
    "accounts/migrations/0002_userprofile_dashboard_layout.py",
    "core/fixed_dashboard_contracts.py",
    "core/test_update131_7_fixed_manager_dashboard_contract.py",
    "INSTALL_OPAL_UPDATE_131_7_FIXED_CRYSTAL_DASHBOARD_AR.md",
    "OPAL_UPDATE_131_7_FIXED_CRYSTAL_DASHBOARD_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_CHANGED_FILES.txt",
    "core/dashboard_truth_contracts.py",
    "core/test_update131_7_r2_dashboard_truth_contract.py",
    "dashboard/management/commands/audit_dashboard_truth.py",
    "INSTALL_OPAL_UPDATE_131_7_R2_DASHBOARD_DATA_INTEGRITY_AR.md",
    "OPAL_UPDATE_131_7_R2_DASHBOARD_DATA_INTEGRITY_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R2_VALIDATION_REPORT_AR.md",
    "core/test_update131_7_r3_student360_mobile_containment_contract.py",
    "INSTALL_OPAL_UPDATE_131_7_R3_STUDENT360_MOBILE_CONTAINMENT_AR.md",
    "OPAL_UPDATE_131_7_R3_STUDENT360_MOBILE_CONTAINMENT_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R3_VALIDATION_REPORT_AR.md",
    "accounting/previous_debt_services.py",
    "accounting/test_previous_debt_services.py",
    "core/test_update131_7_r4_previous_debt_contract.py",
    "templates/accounting/previous_debt_list.html",
    "templates/admissions/previous_debt_payment.html",
    "INSTALL_OPAL_UPDATE_131_7_R4_PREVIOUS_DEBT_AR.md",
    "OPAL_UPDATE_131_7_R4_PREVIOUS_DEBT_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R4_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R4_CHANGED_FILES.txt",
    "INSTALL_OPAL_UPDATE_131_7_R4_1_FEE_BALANCES_CONTRACT_FIX_AR.md",
    "OPAL_UPDATE_131_7_R4_1_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R4_1_VALIDATION_REPORT_AR.md",
    "accounting/test_fee_year_separation.py",
    "core/test_update131_7_r5_fee_year_separation_contract.py",
    "INSTALL_OPAL_UPDATE_131_7_R5_FEE_YEAR_SEPARATION_AR.md",
    "OPAL_UPDATE_131_7_R5_FEE_YEAR_SEPARATION_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R5_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R5_CHANGED_FILES.txt",
    "core/test_update131_7_r6_runtime_stabilization_contract.py",
    "INSTALL_OPAL_UPDATE_131_7_R6_RUNTIME_STABILIZATION_AR.md",
    "OPAL_UPDATE_131_7_R6_RUNTIME_STABILIZATION_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R6_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R6_CHANGED_FILES.txt",
    "core/test_update131_7_r9_production_closeout_contract.py",
    "INSTALL_OPAL_UPDATE_131_7_R9_PRODUCTION_CLOSEOUT_AR.md",
    "OPAL_UPDATE_131_7_R9_PRODUCTION_CLOSEOUT_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R9_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R9_CHANGED_FILES.txt",
    "OPAL_PRODUCTION_ENVIRONMENT_CHECKLIST_R9_AR.md",
    "core/test_update131_7_r10_aesthetic_finishing_contract.py",
    "INSTALL_OPAL_UPDATE_131_7_R10_AESTHETIC_FINISHING_AR.md",
    "OPAL_UPDATE_131_7_R10_AESTHETIC_FINISHING_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R10_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R10_CHANGED_FILES.txt",
    "core/test_update131_7_r11_integrated_learning_platform_contract.py",
    "learning_platform/apps.py",
    "learning_platform/models.py",
    "learning_platform/forms.py",
    "learning_platform/session_auth.py",
    "learning_platform/views.py",
    "learning_platform/urls.py",
    "learning_platform/tests.py",
    "learning_platform/migrations/0001_initial.py",
    "templates/learning_platform/base.html",
    "templates/learning_platform/landing.html",
    "templates/learning_platform/login.html",
    "templates/learning_platform/register.html",
    "templates/learning_platform/dashboard.html",
    "templates/learning_platform/subscriptions.html",
    "static/learning_platform/css/platform.css",
    "static/learning_platform/js/platform.js",
    "INSTALL_OPAL_UPDATE_131_7_R11_INTEGRATED_LEARNING_PLATFORM_AR.md",
    "OPAL_UPDATE_131_7_R11_INTEGRATED_LEARNING_PLATFORM_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R11_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R11_CHANGED_FILES.txt",
    "core/test_update131_7_r12_learning_platform_manager_gateway_contract.py",
    "templates/learning_platform/manager_dashboard.html",
    "INSTALL_OPAL_UPDATE_131_7_R12_LEARNING_PLATFORM_MANAGER_GATEWAY_AR.md",
    "OPAL_UPDATE_131_7_R12_LEARNING_PLATFORM_MANAGER_GATEWAY_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R12_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R12_CHANGED_FILES.txt",
    "core/test_update131_7_r13_learning_platform_manager_runtime_fix_contract.py",
    "INSTALL_OPAL_UPDATE_131_7_R13_LEARNING_PLATFORM_MANAGER_RUNTIME_FIX_AR.md",
    "OPAL_UPDATE_131_7_R13_LEARNING_PLATFORM_MANAGER_RUNTIME_FIX_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R13_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R13_CHANGED_FILES.txt",
    "core/test_update131_7_r14_learning_platform_content_management_contract.py",
    "templates/learning_platform/_manager_nav.html",
    "templates/learning_platform/manager_form.html",
    "templates/learning_platform/manager_account_list.html",
    "templates/learning_platform/manager_subject_list.html",
    "templates/learning_platform/manager_course_list.html",
    "templates/learning_platform/manager_lesson_list.html",
    "INSTALL_OPAL_UPDATE_131_7_R14_LEARNING_PLATFORM_CONTENT_MANAGEMENT_AR.md",
    "OPAL_UPDATE_131_7_R14_LEARNING_PLATFORM_CONTENT_MANAGEMENT_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R14_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R14_CHANGED_FILES.txt",
    "core/test_update131_7_r15_learning_platform_arabic_slug_runtime_fix_contract.py",
    "INSTALL_OPAL_UPDATE_131_7_R15_LEARNING_PLATFORM_ARABIC_SLUG_RUNTIME_FIX_AR.md",
    "OPAL_UPDATE_131_7_R15_LEARNING_PLATFORM_ARABIC_SLUG_RUNTIME_FIX_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R15_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R15_CHANGED_FILES.txt",
    "core/test_update131_7_r16_learning_operations_progress_contract.py",
    "learning_platform/migrations/0002_learninglessonprogress_and_operational_events.py",
    "templates/learning_platform/course_detail.html",
    "templates/learning_platform/lesson_detail.html",
    "templates/learning_platform/manager_subscription_list.html",
    "templates/learning_platform/manager_enrollment_list.html",
    "INSTALL_OPAL_UPDATE_131_7_R16_LEARNING_OPERATIONS_PROGRESS_AR.md",
    "OPAL_UPDATE_131_7_R16_LEARNING_OPERATIONS_PROGRESS_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R16_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R16_CHANGED_FILES.txt",
    "core/test_update131_7_r17_learning_assessments_certificates_contract.py",
    "learning_platform/migrations/0003_learning_assessments_submissions_certificates.py",
    "templates/learning_platform/assessment_detail.html",
    "templates/learning_platform/certificate.html",
    "templates/learning_platform/certificate_verify.html",
    "templates/learning_platform/manager_assessment_list.html",
    "templates/learning_platform/manager_submission_list.html",
    "INSTALL_OPAL_UPDATE_131_7_R17_ASSESSMENTS_GRADING_CERTIFICATES_AR.md",
    "OPAL_UPDATE_131_7_R17_ASSESSMENTS_GRADING_CERTIFICATES_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R17_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R17_CHANGED_FILES.txt",
    "core/test_update131_7_r18_recovery_notifications_reports_contract.py",
    "config/email_registry.py",
    "learning_platform/migrations/0004_account_recovery_notifications.py",
    "templates/learning_platform/password_reset_request.html",
    "templates/learning_platform/password_reset_done.html",
    "templates/learning_platform/password_reset_confirm.html",
    "templates/learning_platform/notifications.html",
    "templates/learning_platform/manager_password_reset_requests.html",
    "templates/learning_platform/manager_account_password_reset.html",
    "templates/learning_platform/manager_reports.html",
    "INSTALL_OPAL_UPDATE_131_7_R18_ACCOUNT_RECOVERY_NOTIFICATIONS_REPORTS_AR.md",
    "OPAL_UPDATE_131_7_R18_ACCOUNT_RECOVERY_NOTIFICATIONS_REPORTS_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R18_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R18_CHANGED_FILES.txt",
    "core/test_update131_7_r19_grounded_ai_governance_contract.py",
    "config/learning_ai_registry.py",
    "learning_platform/ai_services.py",
    "learning_platform/migrations/0005_learning_ai_governance.py",
    "templates/learning_platform/manager_ai_center.html",
    "templates/learning_platform/ai_assistant.html",
    "templates/learning_platform/teacher_ai_workspace.html",
    "INSTALL_OPAL_UPDATE_131_7_R19_GROUNDED_AI_ASSISTANT_TEACHER_TOOLS_AR.md",
    "OPAL_UPDATE_131_7_R19_VALIDATION_REPORT_AR.md",
    "core/test_update131_7_r20_learning_production_release_contract.py",
    "learning_platform/migrations/0006_learning_production_release.py",
    "learning_platform/security_services.py",
    "learning_platform/payment_services.py",
    "learning_platform/api.py",
    "learning_platform/production.py",
    "learning_platform/management/commands/verify_learning_production_readiness.py",
    "learning_platform/management/commands/backup_learning_platform.py",
    "learning_platform/management/commands/verify_learning_backup.py",
    "templates/learning_platform/legal_acceptance.html",
    "templates/learning_platform/manager_readiness.html",
    "templates/learning_platform/manager_plan_list.html",
    "templates/learning_platform/manager_payment_list.html",
    "templates/learning_platform/manifest.webmanifest",
    "templates/learning_platform/service-worker.js",
    "docs/LEARNING_MOBILE_API_V1_AR.md",
    "docs/LEARNING_PRODUCTION_RUNBOOK_R20_AR.md",
    "docs/LEARNING_POSTGRESQL_MIGRATION_R20_AR.md",
    "mobile/opal_learning_app/pubspec.yaml",
    "mobile/opal_learning_app/lib/main.dart",
    "INSTALL_OPAL_UPDATE_131_7_R20_LEARNING_PLATFORM_PRODUCTION_RELEASE_CANDIDATE_AR.md",
    "OPAL_UPDATE_131_7_R20_LEARNING_PLATFORM_PRODUCTION_RELEASE_CANDIDATE_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R20_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R20_CHANGED_FILES.txt",
    "learning_platform/migrations/0007_r21_runtime_validation_fixes.py",
    "core/test_update131_7_r21_learning_runtime_validation_fix_contract.py",
    "INSTALL_OPAL_UPDATE_131_7_R21_LEARNING_RUNTIME_VALIDATION_FIXES_AR.md",
    "OPAL_UPDATE_131_7_R21_LEARNING_RUNTIME_VALIDATION_FIXES_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R21_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R21_CHANGED_FILES.txt",
    "core/release_contract_assertions.py",
    "core/test_update131_7_r22_forward_compatible_release_contract.py",
    "INSTALL_OPAL_UPDATE_131_7_R22_FORWARD_COMPATIBLE_RELEASE_CONTRACT_FIX_AR.md",
    "OPAL_UPDATE_131_7_R22_FORWARD_COMPATIBLE_RELEASE_CONTRACT_FIX_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R22_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R22_CHANGED_FILES.txt",
    "core/migrations/0012_r23_release_identity_sync.py",
    "core/test_update131_7_r23_release_identity_deployment_sync_contract.py",
    "INSTALL_OPAL_UPDATE_131_7_R23_RELEASE_IDENTITY_DEPLOYMENT_SYNC_AR.md",
    "OPAL_UPDATE_131_7_R23_RELEASE_IDENTITY_DEPLOYMENT_SYNC_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R23_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R23_CHANGED_FILES.txt",
    "core/migrations/0013_r24_migration_identity_ordering_fix.py",
    "core/test_update131_7_r24_migration_identity_ordering_fix_contract.py",
    "INSTALL_OPAL_UPDATE_131_7_R24_MIGRATION_IDENTITY_ORDERING_FIX_AR.md",
    "OPAL_UPDATE_131_7_R24_MIGRATION_IDENTITY_ORDERING_FIX_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R24_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R24_CHANGED_FILES.txt",
    "core/test_update131_7_r25_core_test_stability_legacy_contract.py",
    "INSTALL_OPAL_UPDATE_131_7_R25_CORE_TEST_STABILITY_LEGACY_CONTRACT_FIX_AR.md",
    "OPAL_UPDATE_131_7_R25_CORE_TEST_STABILITY_LEGACY_CONTRACT_FIX_RELEASE_NOTES_AR.md",
    "OPAL_UPDATE_131_7_R25_VALIDATION_REPORT_AR.md",
    "OPAL_UPDATE_131_7_R25_CHANGED_FILES.txt",
}
FORBIDDEN_PARTS = {
    ".git", ".venv", "venv", "env", "media", "uploads", "staticfiles",
    "collected_static", "__pycache__", ".pytest_cache", "backups", "backup",
}
FORBIDDEN_NAMES = {"db.sqlite3", ".env", ".coverage"}
FORBIDDEN_SUFFIXES = {
    ".sqlite", ".sqlite3", ".db", ".pyc", ".pyo", ".pyd", ".zip", ".tar",
    ".tgz", ".bak", ".backup", ".log",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path: Path) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    if not path.is_file() or not zipfile.is_zipfile(path):
        return {"ok": False, "archive": str(path), "errors": ["الملف ليس ZIP صالحًا."], "warnings": []}

    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            errors.append(f"عضو تالف داخل الحزمة: {bad}")
        raw_names = [item.filename.replace("\\", "/") for item in archive.infolist()]
        file_names = {name.rstrip("/") for name in raw_names if name and not name.endswith("/")}

        manage_candidates = [name for name in file_names if name == "manage.py" or name.endswith("/manage.py")]
        if len(manage_candidates) != 1:
            errors.append("يجب أن تحتوي الحزمة على مشروع واحد وملف manage.py واحد.")
            prefix = ""
        else:
            manage = PurePosixPath(manage_candidates[0])
            prefix = "" if str(manage.parent) == "." else f"{manage.parent.as_posix()}/"

        normalized = set()
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            pure = PurePosixPath(name)
            if not name or pure.is_absolute() or ".." in pure.parts:
                errors.append(f"مسار غير آمن: {name!r}")
                continue
            unix_mode = (info.external_attr >> 16) & 0o170000
            if unix_mode == 0o120000:
                errors.append(f"رابط رمزي محظور: {name}")
            relative = name[len(prefix):] if prefix and name.startswith(prefix) else name
            relative = relative.rstrip("/")
            if not relative:
                continue
            normalized.add(relative)
            parts = PurePosixPath(relative).parts
            lowered_parts = {part.lower() for part in parts}
            basename = parts[-1]
            suffix = PurePosixPath(basename).suffix.lower()
            if lowered_parts & {part.lower() for part in FORBIDDEN_PARTS}:
                errors.append(f"مجلد تشغيل/خاص محظور: {relative}")
            if basename in FORBIDDEN_NAMES or (basename.startswith(".env") and basename != ".env.example"):
                errors.append(f"ملف سري أو قاعدة بيانات محظور: {relative}")
            if suffix in FORBIDDEN_SUFFIXES:
                errors.append(f"امتداد محظور داخل الحزمة: {relative}")

        missing = sorted(REQUIRED - normalized)
        if missing:
            errors.append("ملفات مطلوبة مفقودة: " + ", ".join(missing))

        def read_text(relative: str) -> str:
            member = f"{prefix}{relative}" if prefix else relative
            try:
                return archive.read(member).decode("utf-8").strip()
            except (KeyError, UnicodeDecodeError):
                return ""

        if read_text("OPAL_VERSION.txt") != EXPECTED_VERSION:
            errors.append("هوية OPAL_VERSION.txt داخل الحزمة ليست 131.7.")
        release_name = read_text("OPAL_RELEASE_NAME.txt")
        if not re.fullmatch(r"OPAL Update 131\.7 R\d+ - .+", release_name):
            errors.append("اسم الإصدار داخل الحزمة لا يطابق هوية Update 131.7.")
        manifest_text = read_text("OPAL_UPDATE_MANIFEST.json")
        try:
            manifest = json.loads(manifest_text)
        except json.JSONDecodeError:
            manifest = {}
            errors.append("OPAL_UPDATE_MANIFEST.json غير صالح.")
        if manifest.get("version") != EXPECTED_VERSION or manifest.get("version_name") != release_name:
            errors.append("بيانات manifest لا تطابق إصدار Update 131.7.")
        if not manifest.get("code_only"):
            errors.append("manifest لا يثبت أن الحزمة code-only.")
        revision = manifest.get("package_revision")
        if not isinstance(revision, int) or revision < MIN_PACKAGE_REVISION:
            errors.append("مراجعة الحزمة الحالية يجب أن تكون 28 أو أحدث لتحديث 131.7.")

    unique_errors = list(dict.fromkeys(errors))
    return {
        "ok": not unique_errors,
        "archive": str(path),
        "sha256": sha256(path),
        "files": len(file_names),
        "errors": unique_errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = verify(Path(args.archive).resolve())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("PASS" if report["ok"] else "FAIL", "OPAL Update 131 archive")
        print(f"- files: {report.get('files', 0)}")
        print(f"- sha256: {report.get('sha256', '')}")
        for warning in report["warnings"]:
            print(f"WARNING: {warning}")
        for error in report["errors"]:
            print(f"ERROR: {error}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
