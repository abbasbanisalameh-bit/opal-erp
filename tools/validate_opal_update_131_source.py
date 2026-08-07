#!/usr/bin/env python3
"""Static acceptance gate for OPAL Update 131.7.

This validator intentionally uses only Python's standard library so it can run
before the Django virtual environment is activated. It does not replace
``manage.py check``, migrations, or the Django test suite.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path


UPDATE = "131.7"
NEXT_UPDATE = "132.0"
MIN_PACKAGE_REVISION = 30


def read(root: Path, relative: str) -> str:
    path = root / relative
    return path.read_text(encoding="utf-8") if path.exists() else ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="Project root (default: current directory)")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    checks: list[dict[str, object]] = []

    def add_check(code: str, ok: bool, detail: str, *, path: str = "") -> None:
        checks.append({"code": code, "ok": ok, "detail": detail, "path": path})
        if not ok:
            errors.append({"code": code, "message": detail, "path": path})

    def require_file(relative: str) -> str:
        path = root / relative
        add_check(f"file:{relative}", path.exists(), f"Required file missing: {relative}", path=relative)
        return read(root, relative)

    # 1) Every Python source file must parse before any framework import occurs.
    syntax_failures = []
    python_files = []
    for path in sorted(root.rglob("*.py")):
        if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            continue
        python_files.append(path)
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            syntax_failures.append(f"{path.relative_to(root)}: {exc}")
    add_check(
        "python_syntax",
        not syntax_failures,
        "All Python sources parse successfully." if not syntax_failures else " | ".join(syntax_failures),
    )

    # 2) Release identity and cache-busting must be coherent.
    version = require_file("OPAL_VERSION.txt").strip()
    add_check("version", version == UPDATE, f"OPAL_VERSION.txt must equal {UPDATE}; found {version!r}.", path="OPAL_VERSION.txt")
    release_name = require_file("OPAL_RELEASE_NAME.txt").strip()
    add_check(
        "release_name",
        bool(re.fullmatch(r"OPAL Update 131\.7 R\d+ - .+", release_name)),
        f"OPAL_RELEASE_NAME.txt must identify an Update 131.7 revision; found {release_name!r}.",
        path="OPAL_RELEASE_NAME.txt",
    )
    update_runtime = require_file("core/update_engine_runtime.py")
    add_check(
        "release_identity_authority",
        "def _code_release_identity" in update_runtime and "name = code_name or" in update_runtime,
        "The Update Center must prefer the release identity shipped by the source tree over a stale private marker.",
        path="core/update_engine_runtime.py",
    )
    manifest_text = require_file("OPAL_UPDATE_MANIFEST.json")
    try:
        manifest = json.loads(manifest_text)
    except json.JSONDecodeError:
        manifest = {}
    add_check(
        "release_manifest",
        manifest.get("version") == UPDATE
        and manifest.get("version_name") == release_name
        and manifest.get("code_only") is True
        and isinstance(manifest.get("package_revision"), int)
        and manifest.get("package_revision") >= MIN_PACKAGE_REVISION,
        "OPAL_UPDATE_MANIFEST.json must match the source release name and identify a code-only verified package at revision 28 or later.",
        path="OPAL_UPDATE_MANIFEST.json",
    )
    require_file("INSTALL_OPAL_UPDATE_131_7_R4_1_FEE_BALANCES_CONTRACT_FIX_AR.md")
    require_file("OPAL_UPDATE_131_7_R4_1_RELEASE_NOTES_AR.md")
    require_file("OPAL_UPDATE_131_7_R4_1_VALIDATION_REPORT_AR.md")
    require_file("INSTALL_OPAL_UPDATE_131_7_R5_FEE_YEAR_SEPARATION_AR.md")
    require_file("OPAL_UPDATE_131_7_R5_FEE_YEAR_SEPARATION_RELEASE_NOTES_AR.md")
    require_file("OPAL_UPDATE_131_7_R5_VALIDATION_REPORT_AR.md")
    require_file("OPAL_UPDATE_131_7_R5_CHANGED_FILES.txt")
    require_file("INSTALL_OPAL_UPDATE_131_7_R6_RUNTIME_STABILIZATION_AR.md")
    require_file("OPAL_UPDATE_131_7_R6_RUNTIME_STABILIZATION_RELEASE_NOTES_AR.md")
    require_file("OPAL_UPDATE_131_7_R6_VALIDATION_REPORT_AR.md")
    require_file("OPAL_UPDATE_131_7_R6_CHANGED_FILES.txt")
    require_file("core/test_update131_7_r9_production_closeout_contract.py")
    require_file("INSTALL_OPAL_UPDATE_131_7_R9_PRODUCTION_CLOSEOUT_AR.md")
    require_file("OPAL_UPDATE_131_7_R9_PRODUCTION_CLOSEOUT_RELEASE_NOTES_AR.md")
    require_file("OPAL_UPDATE_131_7_R9_VALIDATION_REPORT_AR.md")
    require_file("OPAL_UPDATE_131_7_R9_CHANGED_FILES.txt")
    require_file("OPAL_PRODUCTION_ENVIRONMENT_CHECKLIST_R9_AR.md")
    require_file("core/test_update131_7_r10_aesthetic_finishing_contract.py")
    require_file("INSTALL_OPAL_UPDATE_131_7_R10_AESTHETIC_FINISHING_AR.md")
    require_file("OPAL_UPDATE_131_7_R10_AESTHETIC_FINISHING_RELEASE_NOTES_AR.md")
    require_file("OPAL_UPDATE_131_7_R10_VALIDATION_REPORT_AR.md")
    require_file("OPAL_UPDATE_131_7_R10_CHANGED_FILES.txt")
    require_file("core/test_update131_7_r11_integrated_learning_platform_contract.py")
    require_file("learning_platform/migrations/0001_initial.py")
    learning_models = require_file("learning_platform/models.py")
    learning_session = require_file("learning_platform/session_auth.py")
    learning_base = require_file("templates/learning_platform/base.html")
    require_file("static/learning_platform/css/platform.css")
    require_file("static/learning_platform/js/platform.js")
    require_file("INSTALL_OPAL_UPDATE_131_7_R11_INTEGRATED_LEARNING_PLATFORM_AR.md")
    require_file("OPAL_UPDATE_131_7_R11_INTEGRATED_LEARNING_PLATFORM_RELEASE_NOTES_AR.md")
    require_file("OPAL_UPDATE_131_7_R11_VALIDATION_REPORT_AR.md")
    require_file("OPAL_UPDATE_131_7_R11_CHANGED_FILES.txt")
    require_file("core/test_update131_7_r12_learning_platform_manager_gateway_contract.py")
    learning_views = require_file("learning_platform/views.py")
    learning_urls = require_file("learning_platform/urls.py")
    learning_manager_template = require_file("templates/learning_platform/manager_dashboard.html")
    workflow_catalog = require_file("core/workflow_catalog.py")
    require_file("INSTALL_OPAL_UPDATE_131_7_R12_LEARNING_PLATFORM_MANAGER_GATEWAY_AR.md")
    require_file("OPAL_UPDATE_131_7_R12_LEARNING_PLATFORM_MANAGER_GATEWAY_RELEASE_NOTES_AR.md")
    require_file("OPAL_UPDATE_131_7_R12_VALIDATION_REPORT_AR.md")
    require_file("OPAL_UPDATE_131_7_R12_CHANGED_FILES.txt")
    require_file("core/test_update131_7_r13_learning_platform_manager_runtime_fix_contract.py")
    require_file("INSTALL_OPAL_UPDATE_131_7_R13_LEARNING_PLATFORM_MANAGER_RUNTIME_FIX_AR.md")
    require_file("OPAL_UPDATE_131_7_R13_LEARNING_PLATFORM_MANAGER_RUNTIME_FIX_RELEASE_NOTES_AR.md")
    require_file("OPAL_UPDATE_131_7_R13_VALIDATION_REPORT_AR.md")
    require_file("OPAL_UPDATE_131_7_R13_CHANGED_FILES.txt")
    require_file("core/test_update131_7_r14_learning_platform_content_management_contract.py")
    learning_forms = require_file("learning_platform/forms.py")
    learning_manager_accounts = require_file("templates/learning_platform/manager_account_list.html")
    learning_manager_subjects = require_file("templates/learning_platform/manager_subject_list.html")
    learning_manager_courses = require_file("templates/learning_platform/manager_course_list.html")
    learning_manager_lessons = require_file("templates/learning_platform/manager_lesson_list.html")
    require_file("templates/learning_platform/manager_form.html")
    require_file("templates/learning_platform/_manager_nav.html")
    require_file("INSTALL_OPAL_UPDATE_131_7_R14_LEARNING_PLATFORM_CONTENT_MANAGEMENT_AR.md")
    require_file("OPAL_UPDATE_131_7_R14_LEARNING_PLATFORM_CONTENT_MANAGEMENT_RELEASE_NOTES_AR.md")
    require_file("OPAL_UPDATE_131_7_R14_VALIDATION_REPORT_AR.md")
    require_file("OPAL_UPDATE_131_7_R14_CHANGED_FILES.txt")
    require_file("core/test_update131_7_r15_learning_platform_arabic_slug_runtime_fix_contract.py")
    require_file("INSTALL_OPAL_UPDATE_131_7_R15_LEARNING_PLATFORM_ARABIC_SLUG_RUNTIME_FIX_AR.md")
    require_file("OPAL_UPDATE_131_7_R15_LEARNING_PLATFORM_ARABIC_SLUG_RUNTIME_FIX_RELEASE_NOTES_AR.md")
    require_file("OPAL_UPDATE_131_7_R15_VALIDATION_REPORT_AR.md")
    require_file("OPAL_UPDATE_131_7_R15_CHANGED_FILES.txt")
    add_check(
        "learning_platform_unicode_course_slug_runtime",
        'path("courses/<str:slug>/", views.course_detail, name="course_detail")' in learning_urls
        and 'courses/<slug:slug>/' not in learning_urls
        and "def test_arabic_course_slug_renders_public_and_manager_surfaces" in require_file("learning_platform/tests.py")
        and "allow_unicode=True" in learning_forms
        and not (root / "learning_platform/migrations/0002_arabic_slug_fix.py").exists(),
        "R15 must align the public course route with the existing Unicode-capable slug fields, cover Arabic identifiers at runtime, and remain migration-free.",
        path="learning_platform/urls.py",
    )
    add_check(
        "learning_platform_content_management",
        "class LearningTeacherCreateForm" in learning_forms
        and "class LearningSubjectForm" in learning_forms
        and "class LearningCourseForm" in learning_forms
        and "class LearningLessonForm" in learning_forms
        and 'name="manager_teacher_create"' in learning_urls
        and 'name="manager_course_create"' in learning_urls
        and 'name="manager_lesson_create"' in learning_urls
        and "def platform_manager_required" in learning_views
        and "@require_POST\ndef manager_account_toggle" in learning_views
        and "@require_POST\ndef manager_course_status" in learning_views
        and "course.lessons.filter(is_published=True).exists()" in learning_views
        and "الحسابات والمدرّسون" in learning_manager_accounts
        and "المواد التعليمية" in learning_manager_subjects
        and "الدورات والدروس" in learning_manager_courses
        and "دروس:" in learning_manager_lessons,
        "R14 must provide manager-only teacher, subject, course and lesson management with POST-protected state changes and a minimum-content publish gate.",
        path="learning_platform/views.py",
    )
    add_check(
        "learning_platform_no_parallel_schema_r14",
        not (root / "learning_platform/migrations/0002_content_management.py").exists()
        and "class PlatformTeacher" not in learning_models
        and "class PlatformStudent" not in learning_models,
        "R14 must use the existing learning-platform models and must not create parallel teacher/student models or an unnecessary schema migration.",
        path="learning_platform/models.py",
    )
    add_check(
        "learning_platform_manager_runtime_import",
        "LearningAccount," in learning_views
        and "accounts = LearningAccount.objects.all()" in learning_views,
        "learning_platform.views.manager_dashboard must import LearningAccount before querying it, otherwise /learning/manage/ returns HTTP 500.",
        path="learning_platform/views.py",
    )
    add_check(
        "learning_platform_manager_gateway",
        '@login_required(login_url="login")' in learning_views
        and "is_management_user(request.user)" in learning_views
        and 'path("manage/", views.manager_dashboard, name="manager_dashboard")' in learning_urls
        and '"learning-platform"' in workflow_catalog
        and '"learning_platform:manager_dashboard"' in workflow_catalog
        and "إدارة منصة أوبال التعليمية" in learning_manager_template,
        "The learning platform manager gateway must use the OPAL ERP management identity and remain visible in canonical navigation.",
        path="learning_platform/views.py",
    )
    add_check(
        "integrated_learning_platform_isolation",
        "class LearningAccount(models.Model):" in learning_models
        and "class Student(" not in learning_models
        and "students.Student" not in learning_models
        and 'LEARNING_SESSION_KEY = "opal_learning_account_id"' in learning_session
        and "base/base.html" not in learning_base
        and "includes/sidebar.html" not in learning_base
        and "includes/topbar.html" not in learning_base
        and "learning_platform/css/platform.css" in learning_base,
        "The integrated learning platform must keep its identity, session, student records and visual shell independent from OPAL ERP.",
        path="learning_platform/models.py",
    )
    base = require_file("templates/base/base.html")
    primary_tokens = re.findall(
        r"(?:opal_erp\.css|opal_dashboard_executive\.css|opal_entity_360_consolidation\.css|opal_erp\.js)' %\}\?v=([^\"\s]+)",
        base,
    )
    add_check(
        "cache_token",
        len(primary_tokens) == 4 and len(set(primary_tokens)) == 1,
        "The four primary CSS/JS references must share one non-empty cache token.",
        path="templates/base/base.html",
    )
    entity_css = require_file("static/css/opal_entity_360_consolidation.css")
    student_360 = require_file("templates/students/student_360.html")
    add_check(
        "student360_mobile_width_containment",
        'class="tab-content opal-student-360-tab-content"' in student_360
        and "OPAL Update 131.7 R3 — Student 360 mobile width containment" in entity_css
        and ".opal-student-360 .opal-student-360-tab-content" in entity_css
        and "overflow-x:auto!important" in entity_css
        and "contain:inline-size" in entity_css
        and "css/opal_entity_360_consolidation.css" in base,
        "Student 360 wide tabs must remain viewport-contained and scroll only inside their data wrapper.",
        path="static/css/opal_entity_360_consolidation.css",
    )
    subject_ui_contract = require_file("core/subject_ui_contracts.py")
    add_check(
        "manager_dashboard_asset_contract",
        "css/opal_dashboard_executive.css" in base
        and '"css/opal_dashboard_executive.css"' in subject_ui_contract
        and "update1317-fixed-crystal-dashboard" not in subject_ui_contract,
        "The subject UI system check must validate the real manager-dashboard stylesheet path, not a volatile cache token.",
        path="core/subject_ui_contracts.py",
    )

    # 2b) Teacher list must import the official TPI snapshot model it queries.
    teacher_views = require_file("teachers/views.py")
    add_check(
        "teacher_list_tpi_snapshot_import",
        "TeacherPerformanceSnapshot" in teacher_views
        and "from .models import Homework, Teacher, TeacherAssignment, TeacherPerformanceSnapshot" in teacher_views,
        "teachers.teacher_list queries TeacherPerformanceSnapshot and must import it to avoid HTTP 500.",
        path="teachers/views.py",
    )
    teacher_list_block = teacher_views[
        teacher_views.index("def teacher_list"):
        teacher_views.index("def teacher_create")
    ]
    add_check(
        "teacher_list_read_only_tpi",
        "management_tpi_context" not in teacher_list_block
        and "TeacherPerformanceSnapshot.objects.filter" in teacher_list_block
        and "period=tpi_period" in teacher_list_block,
        "The teacher list must read the current monthly TPI snapshots without recalculating the whole school on every request.",
        path="teachers/views.py",
    )
    teacher_list_template = require_file("templates/teachers/teacher_list.html")
    add_check(
        "teacher_impersonation_action_restored",
        "accounts:impersonate_user" in teacher_list_template
        and "request.user.is_superuser" in teacher_list_template
        and "الدخول بحسابه" in teacher_list_template,
        "The manager-only teacher impersonation action must remain available for active linked teacher accounts.",
        path="templates/teachers/teacher_list.html",
    )

    # 2c) Post-consolidation page rendering must remain read-only and scoped.
    notification_context = require_file("enterprise_ops/context_processors.py")
    add_check(
        "global_notification_context_read_only",
        "sync_attendance_registers" not in notification_context
        and not any(token in notification_context for token in (
            ".save(", ".create(", ".update(", ".delete(",
            "get_or_create(", "update_or_create(", "bulk_create(",
        )),
        "The notification context processor must never synchronize or write operational data on every page.",
        path="enterprise_ops/context_processors.py",
    )
    timetable_context = require_file("timetable/context_processors.py")
    add_check(
        "compact_management_topbar_status",
        "school_live_status" in timetable_context
        and "management_live_status" not in timetable_context,
        "The global management topbar must use compact school status rather than the full management dashboard state.",
        path="timetable/context_processors.py",
    )
    add_check(
        "teacher_management_school_scope",
        "school = request_school(request)" in teacher_views
        and "Teacher.objects.filter(school=school)" in teacher_views
        and "teacher__school=school" in teacher_views,
        "Teacher management queries must be scoped to the active request school.",
        path="teachers/views.py",
    )
    dashboard_block = teacher_views[
        teacher_views.index("def dashboard"):
        teacher_views.index("def teacher_list")
    ]
    add_check(
        "management_tpi_explicit_refresh",
        "management_tpi_snapshot_context" in dashboard_block
        and 'request.method == "POST"' in dashboard_block
        and 'request.POST.get("action") == "refresh_tpi"' in dashboard_block
        and "management_tpi_context(school=school)" in dashboard_block,
        "The teachers dashboard must read TPI snapshots on GET and recalculate only through an explicit POST action.",
        path="teachers/views.py",
    )
    portal_block = teacher_views[
        teacher_views.index("def portal_dashboard"):
        teacher_views.index("def portal_workspace")
    ]
    add_check(
        "teacher_portal_tpi_read_only",
        "teacher_tpi_snapshot_context" in portal_block
        and "teacher_tpi_context(" not in portal_block,
        "The teacher portal must read the current TPI snapshot without recalculating the whole school on login.",
        path="teachers/views.py",
    )
    post_contracts = require_file("core/post_consolidation_contracts.py")
    core_checks = require_file("core/checks.py")
    add_check(
        "post_consolidation_system_gate",
        "run_post_consolidation_stability_audit" in post_contracts
        and "run_post_consolidation_stability_audit" in core_checks
        and 'id="opal.E131"' in core_checks,
        "The post-consolidation stability contracts must be registered in Django system checks.",
        path="core/checks.py",
    )
    live_contracts = require_file("core/live_operations_contracts.py")
    dashboard_workflow = require_file("dashboard/workflow.py")
    dashboard_template = require_file("dashboard/templates/dashboard/home.html")
    timetable_workflow = require_file("timetable/workflow.py")
    add_check(
        "live_operations_system_gate",
        "run_live_operations_repair_audit" in live_contracts
        and "run_live_operations_repair_audit" in core_checks
        and 'id="opal.E132"' in core_checks,
        "The live-operations repair contracts must be registered in Django system checks.",
        path="core/checks.py",
    )
    add_check(
        "weekly_teacher_state_scope",
        "decorate_weekly_entries_with_current_status(" in timetable_workflow
        and "def decorate_weekly_entries_with_current_status" in require_file("timetable/attendance_services.py"),
        "Weekly timetable teacher status must be scoped to today's weekday only.",
        path="timetable/workflow.py",
    )
    add_check(
        "director_live_dashboard",
        '"opal_live_schedule": management_live_status(school)' in dashboard_workflow
        and "opal_live_schedule.grade_columns" in dashboard_template
        and "opal_live_schedule.busy_rows" in dashboard_template
        and "opal_live_schedule.free_teachers" in dashboard_template,
        "Director dashboard must render grade events and effective busy/free teachers.",
        path="dashboard/templates/dashboard/home.html",
    )

    # 3) Annual Subject is the only operational curriculum/plan source.
    subject_model = require_file("academics/models.py")
    for token, label in (
        ("academic_year = models.ForeignKey", "annual academic year"),
        ("weekly_periods = models.PositiveSmallIntegerField", "weekly periods"),
        ("is_required = models.BooleanField", "required flag"),
        ("canonical_key = models.CharField", "canonical identity"),
        ("color = models.CharField", "stored colour"),
        ("uniq_subject_name_per_year_grade", "annual name uniqueness"),
        ("uniq_subject_code_per_year_grade", "annual code uniqueness"),
    ):
        add_check(f"subject:{label}", token in subject_model, f"Subject is missing {label}: {token}", path="academics/models.py")
    add_check(
        "subject_protect",
        'on_delete=models.PROTECT' in subject_model,
        "Subject annual-year/grade relationships must use PROTECT.",
        path="academics/models.py",
    )

    curriculum_model = require_file("curriculum/models.py")
    add_check(
        "curriculum_model_removed",
        not re.search(r"^class\s+Curriculum\b", curriculum_model, flags=re.MULTILINE),
        "Operational curriculum.Curriculum model still exists.",
        path="curriculum/models.py",
    )
    teacher_model = require_file("teachers/models.py")
    assignment_block = teacher_model[teacher_model.find("class TeacherAssignment"):]
    add_check(
        "assignment_periods_removed",
        not re.search(r"^\s+weekly_periods\s*=", assignment_block, flags=re.MULTILINE),
        "TeacherAssignment.weekly_periods still creates a second source of truth.",
        path="teachers/models.py",
    )

    runtime_curriculum_imports = []
    for path in python_files:
        relative = path.relative_to(root)
        if "migrations" in relative.parts or relative.as_posix() == "tools/validate_opal_update_131_source.py":
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"(?:from\s+curriculum\.models\s+import\s+.*\bCurriculum\b|import\s+curriculum\.models)", text):
            runtime_curriculum_imports.append(str(relative))
    add_check(
        "no_runtime_curriculum_import",
        not runtime_curriculum_imports,
        "Runtime Curriculum imports remain: " + ", ".join(runtime_curriculum_imports),
    )

    # 4) Required migration chain and irreversible safety contract.
    migration_files = [
        "academics/migrations/0016_annual_subject_plan_stage.py",
        "teachers/migrations/0014_subject_plan_single_source.py",
        "timetable/migrations/0008_subject_plan_protection.py",
        "curriculum/migrations/0003_remove_parallel_curriculum.py",
        "academics/migrations/0017_finalize_annual_subject_plan.py",
        "academics/migrations/0018_alter_subject_canonical_key_alter_subject_grade.py",
    ]
    migration_text = "\n".join(require_file(path) for path in migration_files)
    for token in (
        "migrate_subject_plan",
        "reverse_unavailable",
        'migrations.DeleteModel(name="Curriculum")',
        'name="weekly_periods"',
        "normalize_sections_and_validate",
        "uniq_subject_name_per_year_grade",
        'name="canonical_key"',
        'name="grade"',
        "django.db.models.deletion.PROTECT",
    ):
        add_check(f"migration:{token}", token in migration_text, f"Migration contract missing token: {token}")
    stage_migration = read(root, migration_files[0])
    add_check(
        "migration_colour_reuse",
        "if canonical not in colour_by_key:" in stage_migration and "colour_by_key.setdefault" not in stage_migration,
        "Annual Subject migration must reuse one colour for repeated canonical identities without reallocation.",
        path=migration_files[0],
    )
    final_state_migration = read(root, migration_files[-1])
    add_check(
        "migration_subject_state_sync",
        all(token in final_state_migration for token in (
            'name="canonical_key"',
            'name="grade"',
            "django.db.models.deletion.PROTECT",
        )),
        "The final Subject model state must be represented by migration 0018 so makemigrations --check is clean.",
        path=migration_files[-1],
    )

    # 5) Consolidated timetable and one-release redirect only.
    timetable_views = require_file("timetable/views.py")
    timetable_dashboard = require_file("templates/timetable/dashboard.html")
    add_check(
        "smart_builder_embedded",
        'id="smart-builder"' in timetable_dashboard and 'value="builder_apply"' in timetable_dashboard,
        "Smart builder is not fully embedded in the canonical timetable dashboard.",
        path="templates/timetable/dashboard.html",
    )
    add_check(
        "smart_builder_template_deleted",
        not (root / "templates/timetable/smart_builder.html").exists(),
        "Standalone smart_builder.html must be deleted.",
        path="templates/timetable/smart_builder.html",
    )
    for token in ('response["Deprecation"] = "true"', f'response["Sunset"] = "OPAL Update {NEXT_UPDATE}"'):
        add_check(f"legacy_timetable:{token}", token in timetable_views, f"Legacy timetable redirect is not marked: {token}", path="timetable/views.py")
    add_check(
        "timetable_no_internal_legacy_link",
        "timetable:smart_builder" not in timetable_dashboard,
        "Canonical timetable template still links to the deprecated route.",
        path="templates/timetable/dashboard.html",
    )

    # 6) Consolidated gradebook and one-release redirects.
    exam_urls = require_file("exams/urls.py")
    exam_views = require_file("exams/views.py")
    gradebook = require_file("templates/exams/gradebook.html")
    add_check(
        "canonical_gradebook",
        'path("", views.gradebook, name="exam_list")' in exam_urls,
        "The canonical /exams/ entry is not the unified gradebook.",
        path="exams/urls.py",
    )
    for deleted in ("templates/exams/dashboard.html", "templates/exams/mark_list.html"):
        add_check(f"deleted:{deleted}", not (root / deleted).exists(), f"Parallel exam template still exists: {deleted}", path=deleted)
    add_check(
        "gradebook_sections",
        all(fragment in gradebook for fragment in ('id="marks-review"', 'id="results-analysis"')),
        "Unified gradebook is missing marks-review or normalized-results sections.",
        path="templates/exams/gradebook.html",
    )
    add_check(
        "legacy_exam_headers",
        'response["Deprecation"] = "true"' in exam_views and f'response["Sunset"] = "OPAL Update {NEXT_UPDATE}"' in exam_views,
        "Exam legacy redirects are not explicitly deprecated for one release.",
        path="exams/views.py",
    )

    # 7) Attendance is exception-based and privacy-safe.
    attendance = require_file("timetable/attendance_services.py")
    for token in (
        "No daily ``present`` rows are generated",
        "teacher_unavailable_for_entry",
        "public_teacher_state",
        '"label": "معلم غائب"',
        '"label": "المعلم غير متاح"',
    ):
        add_check(f"attendance:{token}", token in attendance, f"Attendance exception-policy token missing: {token}", path="timetable/attendance_services.py")
    add_check(
        "no_present_row_creation",
        not re.search(r"TeacherAbsence\.objects\.(?:create|get_or_create|update_or_create)\([^)]*status\s*=\s*[\"']present", attendance, flags=re.DOTALL),
        "Attendance service creates daily present rows, which is forbidden.",
        path="timetable/attendance_services.py",
    )

    # 8) Calculations, TPI, ranking ties, naming/search/print policy.
    analytics = require_file("exams/analytics.py")
    add_check("normalized_exam_math", "def _percentage" in analytics and "normalized_mark_rows" in analytics, "Normalized exam percentage helper is missing.", path="exams/analytics.py")
    add_check(
        "all_top_ties",
        "top_students_by_grade" in analytics and 'row["rank"] <= rank_limit' in analytics and 'key = (row["average"], row["exam_count"])' in analytics,
        "Top-student analytics does not preserve all first-place ties.",
        path="exams/analytics.py",
    )
    tpi = require_file("teachers/tpi.py")
    add_check("tpi_version", 'TPI_VERSION = "TPI-131"' in tpi, "TPI version is not TPI-131.", path="teachers/tpi.py")
    add_check(
        "tpi_exception_evidence",
        "وفق استثناءات الدوام المعتمدة إداريًا" in tpi,
        "TPI attendance evidence does not disclose the administrative-exception source.",
        path="teachers/tpi.py",
    )
    js = require_file("static/js/opal_erp.js")
    system_data = require_file("core/system_data.py")
    site_preferences = require_file("config/site_preferences.py")
    identity_context = require_file("core/context_processors.py")
    add_check(
        "capacity_seed_counts",
        "DEMO_STUDENT_COUNT = 500" in system_data
        and "DEMO_TEACHER_COUNT = 19" in system_data
        and "DEMO_TEACHER_WEEKLY_LOAD = 25" in system_data
        and "DEMO_TEACHER_DAILY_TARGET = 5" in system_data,
        "The integrated data button must create 500 students and the exact 19-teacher/25-period/5-daily capacity dataset.",
        path="core/system_data.py",
    )
    add_check(
        "requested_subject_plan",
        all(token in system_data for token in (
            '("التربية الرياضية", 3)', '("التربية المهنية", 2)', '("التربية الفنية", 1)',
            '("العلوم", 4)', '("الاجتماعيات", 3)', '("الفيزياء", 1)', '("الكيمياء", 1)',
            '("الأحياء", 1)', '("علوم الأرض", 1)', '("التاريخ", 1)', '("الجغرافيا", 1)',
            '("التربية الوطنية", 1)', '("الثقافة المالية", 1)',
        ))
        and 'if grade_order <= 3:' in system_data
        and 'if grade_order <= 9:' in system_data,
        "The seeded subject substitutions and weekly periods do not match the approved plan.",
        path="core/system_data.py",
    )
    add_check(
        "exact_teacher_workload_seed",
        'set(teacher_loads.values()) != {DEMO_TEACHER_WEEKLY_LOAD}' in system_data
        and 'enforce_daily_teaching_target=True' in system_data
        and 'teacher.daily_free_periods = 1' in system_data,
        "Every generated teacher must receive 25 weekly periods, five daily periods, and an editable daily-free policy.",
        path="core/system_data.py",
    )
    add_check(
        "jordan_authoritative_clock",
        'OPAL_TIME_ZONE' in site_preferences
        and '"Asia/Amman"' in site_preferences
        and 'opal_server_now' in identity_context
        and 'data-opal-time-zone' in base
        and 'data-opal-server-now' in base
        and 'opalServerStart' in js
        and 'timeZone: opalClockZone' in js,
        "The whole UI clock must use the server-authoritative school time zone with Asia/Amman as the Irbid default.",
        path="static/js/opal_erp.js",
    )
    subject_identity = require_file("academics/subject_identity.py")
    try:
        identity_tree = ast.parse(subject_identity, filename="academics/subject_identity.py")
        palette_values = []
        semantic_values = []
        for node in identity_tree.body:
            if isinstance(node, ast.Assign):
                names = {target.id for target in node.targets if isinstance(target, ast.Name)}
                if "SUBJECT_PALETTE" in names and isinstance(node.value, (ast.Tuple, ast.List)):
                    palette_values = [item.value for item in node.value.elts if isinstance(item, ast.Constant)]
                if "_SEMANTIC_COLOUR_NAMES" in names and isinstance(node.value, ast.Dict):
                    semantic_values = [
                        value.value for value in node.value.values if isinstance(value, ast.Constant)
                    ]
        def rgb(value):
            return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))
        def distance(first, second):
            left, right = rgb(first), rgb(second)
            return sum((a - b) ** 2 for a, b in zip(left, right)) ** 0.5
        palette_minimum = min(
            distance(first, second)
            for index, first in enumerate(palette_values)
            for second in palette_values[index + 1:]
        ) if len(palette_values) > 1 else 0
        palette_ok = (
            len(palette_values) >= 30
            and len(set(palette_values)) == len(palette_values)
            and palette_minimum >= 45
            and set(semantic_values).issubset(set(palette_values))
        )
    except (SyntaxError, ValueError, TypeError):
        palette_ok = False
    add_check(
        "capacity_subject_palette",
        palette_ok
        and "audit_capacity_subject_palette" in require_file("core/capacity_timezone_contracts.py")
        and "test_capacity_subjects_allocate_without_exhaustion" in require_file("core/test_update131_3_1_subject_palette_contract.py"),
        "The subject palette must safely allocate all 18 capacity identities with at least 45 RGB distance and future headroom.",
        path="academics/subject_identity.py",
    )
    capacity_contracts = require_file("core/capacity_timezone_contracts.py")
    add_check(
        "capacity_timezone_system_gate",
        "run_capacity_timezone_audit" in capacity_contracts
        and "run_capacity_timezone_audit" in core_checks
        and 'id="opal.E133"' in core_checks,
        "The capacity and authoritative-time contracts must be registered in Django system checks.",
        path="core/checks.py",
    )
    live_matrix_contracts = require_file("core/live_events_matrix_contracts.py")
    live_matrix_test = require_file("core/test_update131_4_live_events_matrix_contract.py")
    add_check(
        "live_events_matrix_system_gate",
        "run_live_events_matrix_audit" in live_matrix_contracts
        and "run_live_events_matrix_audit" in core_checks
        and 'id="opal.E134"' in core_checks
        and "Update1314LiveEventsMatrixContractTests" in live_matrix_test,
        "The live-events matrix contracts must be registered in Django system checks.",
        path="core/checks.py",
    )
    live_service = require_file("timetable/live_services.py")
    add_check(
        "live_events_horizontal_matrix",
        "opal_live_schedule.grade_columns" in dashboard_template
        and 'colspan="{{ column.section_count }}"' in dashboard_template
        and "opal-live-grade-row" in dashboard_template
        and "opal-live-section-row" in dashboard_template
        and "opal-live-event-row" in dashboard_template
        and '"grade_columns": grade_columns' in live_service,
        "The director dashboard must publish the three-row grade/section/current-event matrix.",
        path="dashboard/templates/dashboard/home.html",
    )
    add_check(
        "official_time_boundary_refresh",
        'data-opal-official-clock="time"' in dashboard_template
        and "function installLiveBoundaryRefresh()" in js
        and "nearestBoundary + 1" in js,
        "The live matrix must display official server time and refresh at the nearest event boundary.",
        path="static/js/opal_erp.js",
    )
    add_check("search_threshold", "bodyRows.length < 30" in js, "General table instant search threshold is not 30 rows.", path="static/js/opal_erp.js")
    add_check("timetable_search_off", 'data-opal-instant-table="off"' in timetable_dashboard, "Timetable instant search is not disabled.", path="templates/timetable/dashboard.html")
    grade_names = require_file("academics/grade_names.py")
    add_check(
        "section_name_contract",
        'return f"شعبة {text}"' in grade_names,
        "Stored section names are not normalized to the short «شعبة أ» form.",
        path="academics/grade_names.py",
    )
    css = require_file("static/css/opal_erp.css")
    add_check(
        "print_contract",
        "OPAL Update 131" in css and "opal-screen-only" in css and "@media print" in css,
        "Update 131 timetable print contract is incomplete.",
        path="static/css/opal_erp.css",
    )

    workflow_catalog = require_file("core/workflow_catalog.py")
    add_check(
        "single_material_plan_operation",
        '_op("subjects", "academics", "المواد والخطة الدراسية"' in workflow_catalog
        and '_op("curriculum"' not in workflow_catalog
        and '_op("timetable", "academics", "الجدول والمنشئ الذكي"' in workflow_catalog
        and '_op("smart-timetable"' not in workflow_catalog
        and '"exam-analysis"' not in workflow_catalog,
        "The operation catalogue must expose one material/plan operation and no retired exam-analysis key.",
        path="core/workflow_catalog.py",
    )
    try:
        workflow_tree = ast.parse(workflow_catalog, filename="core/workflow_catalog.py")
        operation_keys = set()
        referenced_keys = []
        for node in workflow_tree.body:
            if not isinstance(node, ast.Assign):
                continue
            target_names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            if "OPERATIONS" in target_names and isinstance(node.value, ast.List):
                for item in node.value.elts:
                    if isinstance(item, ast.Call) and item.args and isinstance(item.args[0], ast.Constant):
                        operation_keys.add(item.args[0].value)
            if target_names & {"SIDEBAR_SECTIONS", "MANAGEMENT_SUBNAV_GROUPS"}:
                for item in ast.walk(node.value):
                    if not isinstance(item, ast.Dict):
                        continue
                    for key_node, value_node in zip(item.keys, item.values):
                        if isinstance(key_node, ast.Constant) and key_node.value == "items" and isinstance(value_node, (ast.Tuple, ast.List)):
                            referenced_keys.extend(
                                value.value for value in value_node.elts if isinstance(value, ast.Constant)
                            )
        unknown_operation_keys = sorted(set(referenced_keys) - operation_keys)
    except (SyntaxError, AttributeError, TypeError):
        unknown_operation_keys = ["workflow-catalog-parse-failed"]
    add_check(
        "operation_reference_integrity",
        not unknown_operation_keys,
        "Navigation references unknown operation keys: " + ", ".join(unknown_operation_keys),
        path="core/workflow_catalog.py",
    )
    academic_gateway = require_file("templates/academics/academic_structure.html")
    add_check(
        "single_gateway_cards",
        academic_gateway.count("academics:subject_list") == 1
        and academic_gateway.count("timetable:dashboard") == 1
        and academic_gateway.count("exams:exam_list") == 1,
        "The academic gateway must render one visible card for each consolidated workflow.",
        path="templates/academics/academic_structure.html",
    )

    # 9) No internal templates may use legacy operational routes.
    forbidden_template_routes = (
        "timetable:smart_builder",
        "exams:gradebook",
        "exams:exam_dashboard",
        "exams:mark_list",
        "curriculum:curriculum_list",
        "curriculum:curriculum_create",
        "curriculum:curriculum_update",
        "curriculum:curriculum_delete",
    )
    template_hits = []
    for path in sorted((root / "templates").rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        for route in forbidden_template_routes:
            if route in text:
                template_hits.append(f"{path.relative_to(root)} -> {route}")
    add_check(
        "no_internal_legacy_routes",
        not template_hits,
        "Deprecated routes are still used internally: " + "; ".join(template_hits),
    )

    # 10) Canonical student model must remain untouched as the sole official model.
    extra_student_models = []
    for path in python_files:
        relative = path.relative_to(root)
        if "migrations" in relative.parts or relative.as_posix() == "students/models.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in {"Student", "StudentRecord"}:
                extra_student_models.append(f"{relative}:{node.lineno}:{node.name}")
    add_check(
        "canonical_student",
        not extra_student_models,
        "A parallel student model was detected: " + ", ".join(extra_student_models),
    )

    # 11) Manager dashboard customization is retired; the fixed dashboard order is canonical.
    dashboard_views = require_file("dashboard/views.py")
    dashboard_template = require_file("dashboard/templates/dashboard/home.html")
    dashboard_workflow = require_file("dashboard/workflow.py")
    dashboard_css = require_file("static/css/opal_dashboard_executive.css")
    fixed_contracts = require_file("core/fixed_dashboard_contracts.py")
    add_check(
        "dashboard_customizer_retired",
        "opal-dashboard-layout-form" not in dashboard_template
        and "opal-dashboard-layout-data" not in dashboard_template
        and "save_dashboard_layout" not in dashboard_views
        and "reset_dashboard_layout" not in dashboard_views
        and not (root / "dashboard/layout.py").exists()
        and not (root / "static/js/opal_dashboard_layout.js").exists(),
        "The manager dashboard customizer and its save/reset runtime must be removed.",
        path="dashboard/templates/dashboard/home.html",
    )
    add_check(
        "fixed_dashboard_structure",
        all(marker in dashboard_template for marker in (
            "opal-fixed-manager-dashboard", "opal-manager-quick-row",
            "opal-teacher-performance-row", "opal-top-students-panel",
            "opal-satisfaction-fixed", "opal-actions-fixed-row",
            "آخر 10 طلاب مسجلين وصفوفهم",
        ))
        and 'latest_enrollments = Enrollment.objects.filter(' in dashboard_workflow
        and "top_students_matrix" in dashboard_workflow,
        "The fixed manager dashboard structure or ten-student/top-grade data contract is incomplete.",
        path="dashboard/templates/dashboard/home.html",
    )
    add_check(
        "fixed_dashboard_visual_contract",
        all(marker in dashboard_css for marker in (
            "OPAL Update 131.7 — fixed crystal manager dashboard",
            ".opal-manager-quick-row", ".opal-fixed-pair",
            "border:1px dashed rgba(216,173,79",
        )),
        "The crystal glass, rounded and dashed-gold visual contract is incomplete.",
        path="static/css/opal_dashboard_executive.css",
    )
    single_entry_contracts = require_file("core/single_entry_contracts.py")
    add_check(
        "dashboard_kpi_contract_is_layout_independent",
        "def _anchor_block_with_class" in single_entry_contracts
        and "_anchor_block_with_class(dashboard, css_class)" in single_entry_contracts
        and "marker = f'<a class=\"dashboard-card {css_class}\"'" not in single_entry_contracts
        and all(f'class="opal-manager-quick-button {name}"' in dashboard_template for name in (
            "opal-kpi-students", "opal-kpi-teachers", "opal-kpi-attendance",
            "opal-kpi-collection", "opal-kpi-outstanding", "opal-kpi-success",
        )),
        "The canonical KPI link audit must validate real anchors and destinations without coupling to one historical CSS class order.",
        path="core/single_entry_contracts.py",
    )
    add_check(
        "dashboard_retired_shortcut_contract_consistency",
        '"enterprise_ops:workflow_list": {"dashboard/templates/dashboard/home.html"}' not in single_entry_contracts
        and 'hidden_dashboard_shortcuts = ("enterprise_ops:workflow_list",)' in single_entry_contracts
        and "enterprise_ops:workflow_list" not in dashboard_template,
        "The retired internal-workflow dashboard shortcut must not remain required by an older single-entry contract.",
        path="core/single_entry_contracts.py",
    )
    system_checks = require_file("core/checks.py")
    add_check(
        "fixed_dashboard_system_gate",
        "run_fixed_dashboard_audit" in system_checks
        and 'id="opal.E137"' in system_checks
        and "run_fixed_dashboard_audit" in fixed_contracts,
        "The fixed dashboard contracts must be registered in Django system checks.",
        path="core/checks.py",
    )

    dashboard_truth_contracts = require_file("core/dashboard_truth_contracts.py")
    dashboard_truth_command = require_file("dashboard/management/commands/audit_dashboard_truth.py")
    satisfaction_service = require_file("enterprise_ops/services.py")
    teacher_eval_service = require_file("parent_portal/evaluation_services.py")
    add_check(
        "dashboard_data_truth_contract",
        all(marker in dashboard_workflow for marker in (
            "build_school_attendance_period_snapshot(period_start, today, school=school, academic_year=academic_year)",
            "Teacher.objects.filter(school=school, is_active=True)",
            "StudentInvoice.objects.filter(academic_year=academic_year)",
            "exam__academic_year=academic_year",
            "finance_data_available", "academic_data_available", "no_recent_payment_total",
        ))
        and "feedback_total = participation_qs.count()" in satisfaction_service
        and "both_positive / paired_total" in satisfaction_service
        and "def monthly_teacher_evaluation_snapshot(today=None, school=None):" in teacher_eval_service
        and "بيانات مباشرة من السجلات المعتمدة" in dashboard_template
        and "لم تُعتمد سجلات حضور الشعب اليوم" in dashboard_template
        and ":[0]" not in dashboard_template
        and "run_dashboard_truth_audit" in dashboard_truth_contracts
        and "class Command" in dashboard_truth_command and "finance_remaining" in dashboard_truth_command
        and "run_dashboard_truth_audit" in system_checks
        and 'id="opal.E138"' in system_checks,
        "Every manager-dashboard value must be school/year scoped, truth-labelled, and protected by a production audit command.",
        path="core/dashboard_truth_contracts.py",
    )

    subject_ui_contracts = require_file("core/subject_ui_contracts.py")
    subject_tags = require_file("core/templatetags/opal_subjects.py")
    shared_css = require_file("static/css/opal_erp.css")
    add_check(
        "canonical_subject_colour_ui",
        all(token in shared_css for token in (
            "OPAL Update 131.6: compact role gateways and canonical subject-colour coverage",
            ".opal-subject-chip", ".opal-subject-card", ".opal-compact-module-grid",
            "grid-template-columns:repeat(3,minmax(0,1fr))!important",
        ))
        and "subject_style" in subject_tags
        and "run_subject_ui_audit" in subject_ui_contracts
        and "run_subject_ui_audit" in system_checks
        and 'id="opal.E136"' in system_checks,
        "Canonical subject colours and compact role gateways must be deployed and guarded by a system check.",
        path="core/subject_ui_contracts.py",
    )

    previous_debt_service = require_file("accounting/previous_debt_services.py")
    previous_debt_manager = require_file("templates/accounting/previous_debt_list.html")
    previous_debt_payment = require_file("templates/admissions/previous_debt_payment.html")
    previous_debt_receipt = require_file("templates/admissions/fee_payment_receipt.html")
    parent_dashboard = require_file("templates/parent_portal/dashboard.html")
    student_dashboard = require_file("templates/students/student_360.html")
    add_check(
        "previous_debt_canonical_finance",
        all(marker in previous_debt_service for marker in (
            "StudentInvoice", "StudentPayment", "FeePaymentAllocation",
            "academic_year__start_date__lt=current_year.start_date",
            'payments__status="posted"', "def create_previous_debt_payment",
            "sync_carry_forward_status_for_invoices",
            "carry_forward_record__source_invoices__isnull=False",
        ))
        and "class PreviousDebt" not in previous_debt_service,
        "Previous-year debt must be derived from canonical invoices/payments without a parallel balance model or duplicate carry target.",
        path="accounting/previous_debt_services.py",
    )
    previous_debt_visible_sources = {
        "templates/students/student_360.html": student_dashboard,
        "templates/parent_portal/dashboard.html": parent_dashboard,
        "templates/parent_portal/student_detail.html": require_file("templates/parent_portal/student_detail.html"),
        "templates/accounting/previous_debt_list.html": previous_debt_manager,
        "templates/admissions/previous_debt_payment.html": previous_debt_payment,
        "templates/admissions/fee_payment_receipt.html": previous_debt_receipt,
        "dashboard/templates/dashboard/home.html": require_file("dashboard/templates/dashboard/home.html"),
    }
    forbidden_previous_fee_terms = ("الذمم", "ذمة")
    language_violations = [
        f"{relative}:{term}"
        for relative, source in previous_debt_visible_sources.items()
        for term in forbidden_previous_fee_terms
        if term in source
    ]
    add_check(
        "previous_fee_plain_school_language",
        not language_violations,
        "Previous-year balances must use plain school-fee language; violations: " + ", ".join(language_violations),
        path="templates/accounting/previous_debt_list.html",
    )
    parent_student_detail = previous_debt_visible_sources["templates/parent_portal/student_detail.html"]
    add_check(
        "previous_fee_parent_single_gateway",
        "opal-previous-debt-pulse" in parent_student_detail
        and "parent_portal:fees" not in parent_student_detail
        and "بوابة ولي الأمر الرئيسية" in parent_student_detail,
        "The child detail may show the balance alert but must not recreate the fees gateway outside the parent home page.",
        path="templates/parent_portal/student_detail.html",
    )

    add_check(
        "previous_debt_manager_parent_receipt_ui",
        "admissions:previous_debt_payment" in student_dashboard
        and "opal-previous-debt-pulse" in parent_dashboard
        and "المتبقي بعد الإيصال" in previous_debt_manager
        and "دفعة من متبقيات الرسوم السابقة" in previous_debt_payment
        and "previous_debt_receipt.is_previous_debt" in previous_debt_receipt
        and "row.academic_year.name" in previous_debt_receipt
        and "row.grade_label" in previous_debt_receipt,
        "Manager and guardian alerts, automatic prior-debt payment, receipt detail, and guardian report must remain present.",
        path="templates/accounting/previous_debt_list.html",
    )

    fee_separation_test = require_file("accounting/test_fee_year_separation.py")
    fee_separation_contract = require_file("core/test_update131_7_r5_fee_year_separation_contract.py")
    fee_services = require_file("admissions/financial_services.py")
    fee_models = require_file("admissions/models.py")
    current_payment_block = fee_services.split("def apply_student_payment", 1)[-1].split(
        "@transaction.atomic", 1
    )[0]
    add_check(
        "current_fee_payment_year_isolation",
        "filter(academic_year=academic_year)" in current_payment_block
        and "carry_forward_record__source_invoices__isnull=False" in current_payment_block
        and "ensure_balance_invoice" not in current_payment_block
        and "رسوم السنة الحالية" in current_payment_block
        and "def student_separated_finance_snapshot" in fee_services,
        "Current-year payments must be restricted to current invoices and expose a separate prior-years snapshot.",
        path="admissions/financial_services.py",
    )
    add_check(
        "fee_receipt_period_classification",
        'CURRENT_YEAR_FEE_NOTE_PREFIX = "دفعة رسوم السنة الحالية"' in fee_models
        and 'PREVIOUS_YEARS_FEE_NOTE_PREFIX = "دفعة من متبقيات الرسوم السابقة"' in fee_models
        and "def payment_period" in fee_models
        and "def payment_period_label" in fee_models,
        "Fee receipts must retain a durable current/previous period label without adding a balance model.",
        path="admissions/models.py",
    )
    separated_templates = {
        relative: require_file(relative)
        for relative in (
            "templates/admissions/fee_payment_form.html",
            "templates/admissions/student_financial_record.html",
            "templates/accounting/dashboard.html",
            "templates/parent_portal/dashboard.html",
            "templates/parent_portal/fees.html",
            "templates/students/student_360.html",
        )
    }
    separation_labels = ("رسوم السنة الحالية", "متبقيات السنوات السابقة", "الإجمالي المطلوب")
    missing_separation_labels = [
        f"{relative}:{label}"
        for relative, source in separated_templates.items()
        for label in separation_labels
        if label not in source
    ]
    add_check(
        "fee_year_separation_ui",
        not missing_separation_labels,
        "Finance surfaces must show current, previous, and combined balances; missing: "
        + ", ".join(missing_separation_labels),
        path="templates/admissions/fee_payment_form.html",
    )
    add_check(
        "fee_year_separation_no_parallel_schema",
        "class PreviousYearBalance" not in fee_models + require_file("accounting/models.py")
        and not (root / "accounting/migrations/0010_fee_year_separation.py").exists()
        and not (root / "admissions/migrations/0014_fee_year_separation.py").exists()
        and "test_family_payment_never_touches_previous_year_invoices" in fee_separation_test
        and "test_current_payment_filters_invoices_by_current_academic_year" in fee_separation_contract,
        "The separation must remain service-level, migration-free, and protected by regression tests.",
        path="accounting/test_fee_year_separation.py",
    )

    # R20 learning-platform production release candidate.
    learning_security = require_file("learning_platform/security_services.py")
    learning_payment = require_file("learning_platform/payment_services.py")
    learning_api = require_file("learning_platform/api.py")
    learning_production = require_file("learning_platform/production.py")
    learning_r20_migration = require_file("learning_platform/migrations/0006_learning_production_release.py")
    learning_r20_contract = require_file("core/test_update131_7_r20_learning_production_release_contract.py")
    require_file("learning_platform/management/commands/verify_learning_production_readiness.py")
    require_file("learning_platform/management/commands/backup_learning_platform.py")
    require_file("learning_platform/management/commands/verify_learning_backup.py")
    require_file("templates/learning_platform/manager_readiness.html")
    require_file("templates/learning_platform/manifest.webmanifest")
    require_file("templates/learning_platform/service-worker.js")
    require_file("docs/LEARNING_MOBILE_API_V1_AR.md")
    require_file("docs/LEARNING_PRODUCTION_RUNBOOK_R20_AR.md")
    require_file("templates/learning_platform/legal_acceptance.html")
    require_file("mobile/opal_learning_app/pubspec.yaml")
    require_file("mobile/opal_learning_app/lib/main.dart")
    require_file("OPAL_UPDATE_131_7_R20_VALIDATION_REPORT_AR.md")
    require_file("OPAL_UPDATE_131_7_R20_CHANGED_FILES.txt")
    add_check(
        "learning_r20_security",
        "def consume_rate_limit" in learning_security
        and "def issue_api_token" in learning_security
        and "def create_email_verification_request" in learning_security
        and "failed_login_count" in learning_models
        and "locked_until" in learning_models,
        "R20 must provide database-backed throttling, login lockout, email verification and expiring hashed API tokens.",
        path="learning_platform/security_services.py",
    )
    add_check(
        "learning_r20_payment",
        "def create_payment_order" in learning_payment
        and "def mark_order_paid" in learning_payment
        and "def verify_webhook_signature" in learning_payment
        and "hmac.compare_digest" in learning_payment
        and "LearningPaymentOrder" in learning_models
        and "LearningPaymentEvent" in learning_models
        and "event_amount != order.amount" in learning_payment
        and "event_currency != order.currency.upper()" in learning_payment,
        "R20 payment orders must be idempotent, signed and activate the canonical subscription entitlement only after confirmed payment.",
        path="learning_platform/payment_services.py",
    )
    add_check(
        "learning_r20_mobile_api",
        "def api_auth_required" in learning_api
        and "def api_login" in learning_api
        and "def api_course_list" in learning_api
        and "def api_assessment_detail" in learning_api
        and "def api_assessment_submit" in learning_api
        and "def api_certificates" in learning_api
        and 'name="api_login"' in learning_urls
        and 'name="api_course_list"' in learning_urls
        and 'name="api_assessment_detail"' in learning_urls
        and 'name="api_certificates"' in learning_urls,
        "R20 must expose a versioned mobile API without sharing the OPAL ERP session.",
        path="learning_platform/api.py",
    )
    add_check(
        "learning_r20_readiness",
        "def collect_learning_readiness_checks" in learning_production
        and "MigrationExecutor" in learning_production
        and "blocking_failures" in learning_production
        and "verified_backup" in learning_production
        and "LearningSubscriptionPlan" in learning_r20_migration
        and "test_signed_payment_webhook_is_idempotent" in require_file("learning_platform/tests.py")
        and "LearningProductionReleaseContractTests" in learning_r20_contract,
        "R20 must include production readiness, migration, runtime regression and source-contract gates.",
        path="learning_platform/production.py",
    )

    # R21 learning-platform runtime validation fixes.
    learning_tests_r21 = require_file("learning_platform/tests.py")
    learning_api_contract_r21 = require_file("core/test_update131_7_r20_learning_production_release_contract.py")
    update_runtime_r21 = require_file("core/update_engine_runtime.py")
    learning_r21_migration = require_file("learning_platform/migrations/0007_r21_runtime_validation_fixes.py")
    learning_r21_contract = require_file("core/test_update131_7_r21_learning_runtime_validation_fix_contract.py")
    require_file("INSTALL_OPAL_UPDATE_131_7_R21_LEARNING_RUNTIME_VALIDATION_FIXES_AR.md")
    require_file("OPAL_UPDATE_131_7_R21_LEARNING_RUNTIME_VALIDATION_FIXES_RELEASE_NOTES_AR.md")
    require_file("OPAL_UPDATE_131_7_R21_VALIDATION_REPORT_AR.md")
    require_file("OPAL_UPDATE_131_7_R21_CHANGED_FILES.txt")
    add_check(
        "learning_r21_runtime_test",
        'self.assertIn("course", form.errors)' in learning_tests_r21
        and 'self.assertContains(response, "اختر اختيارًا صحيحًا")' not in learning_tests_r21,
        "R21 must validate rejected out-of-scope courses structurally, not through a translated Django message.",
        path="learning_platform/tests.py",
    )
    add_check(
        "learning_r21_api_contract",
        'request.META.get("HTTP_AUTHORIZATION")' in learning_api_contract_r21
        and 'startswith("bearer ")' in learning_api_contract_r21,
        "R21 must validate the actual Django META authorization header and Bearer semantics.",
        path="core/test_update131_7_r20_learning_production_release_contract.py",
    )
    add_check(
        "learning_r21_manifest_deployment",
        "child.name == MANIFEST_NAME" not in update_runtime_r21
        and "restore_release_manifest" in learning_r21_migration
        and "LearningRuntimeValidationFixContractTests" in learning_r21_contract,
        "R21 must retain manifests in future Update Center deployments and repair the current R20-based deployment.",
        path="core/update_engine_runtime.py",
    )

    # R22 forward-compatible historical release contracts.
    release_contract_helper_r22 = require_file("core/release_contract_assertions.py")
    learning_r22_contract = require_file("core/test_update131_7_r22_forward_compatible_release_contract.py")
    require_file("INSTALL_OPAL_UPDATE_131_7_R22_FORWARD_COMPATIBLE_RELEASE_CONTRACT_FIX_AR.md")
    require_file("OPAL_UPDATE_131_7_R22_FORWARD_COMPATIBLE_RELEASE_CONTRACT_FIX_RELEASE_NOTES_AR.md")
    require_file("OPAL_UPDATE_131_7_R22_VALIDATION_REPORT_AR.md")
    require_file("OPAL_UPDATE_131_7_R22_CHANGED_FILES.txt")
    historical_contracts_r22 = [
        require_file(str(next((root / "core").glob(f"test_update131_7_r{revision}_*.py")).relative_to(root)))
        for revision in range(11, 22)
    ]
    add_check(
        "learning_r22_forward_compatible_identity_helper",
        "def assert_forward_compatible_release_identity" in release_contract_helper_r22
        and r'r"OPAL Update 131\.7 R\d+ - .+"' in release_contract_helper_r22
        and 'manifest["baseline"]' not in release_contract_helper_r22,
        "R22 must centralize current-release identity without pinning a historical baseline.",
        path="core/release_contract_assertions.py",
    )
    add_check(
        "learning_r22_historical_contracts",
        all("assert_forward_compatible_release_identity" in contract for contract in historical_contracts_r22)
        and all('manifest["baseline"]' not in contract for contract in historical_contracts_r22)
        and "ForwardCompatibleReleaseContractTests" in learning_r22_contract,
        "R22 must make R11-R21 feature contracts executable after later 131.7 revisions.",
        path="core/test_update131_7_r22_forward_compatible_release_contract.py",
    )


    # R23 release identity deployment synchronization.
    release_identity_migration_r23 = require_file("core/migrations/0012_r23_release_identity_sync.py")
    release_identity_contract_r23 = require_file("core/test_update131_7_r23_release_identity_deployment_sync_contract.py")
    require_file("INSTALL_OPAL_UPDATE_131_7_R23_RELEASE_IDENTITY_DEPLOYMENT_SYNC_AR.md")
    require_file("OPAL_UPDATE_131_7_R23_RELEASE_IDENTITY_DEPLOYMENT_SYNC_RELEASE_NOTES_AR.md")
    require_file("OPAL_UPDATE_131_7_R23_VALIDATION_REPORT_AR.md")
    require_file("OPAL_UPDATE_131_7_R23_CHANGED_FILES.txt")
    add_check(
        "learning_r23_release_identity_deployment_sync",
        "RELEASE_IDENTITY_FILES" in update_runtime
        and "def _synchronize_release_identity_from_source" in update_runtime
        and "_synchronize_release_identity_from_source(source_root, root)" in update_runtime
        and "synchronize_release_identity" in release_identity_migration_r23
        and "ReleaseIdentityDeploymentSynchronizationContractTests" in release_identity_contract_r23,
        "R23 must explicitly copy, validate, and repair all release identity files during deployment.",
        path="core/update_engine_runtime.py",
    )

    # R24 migration identity ordering fix.
    learning_r21_migration_r24 = require_file("learning_platform/migrations/0007_r21_runtime_validation_fixes.py")
    release_identity_migration_r24 = require_file("core/migrations/0013_r24_migration_identity_ordering_fix.py")
    release_identity_contract_r24 = require_file("core/test_update131_7_r24_migration_identity_ordering_fix_contract.py")
    require_file("INSTALL_OPAL_UPDATE_131_7_R24_MIGRATION_IDENTITY_ORDERING_FIX_AR.md")
    require_file("OPAL_UPDATE_131_7_R24_MIGRATION_IDENTITY_ORDERING_FIX_RELEASE_NOTES_AR.md")
    require_file("OPAL_UPDATE_131_7_R24_VALIDATION_REPORT_AR.md")
    require_file("OPAL_UPDATE_131_7_R24_CHANGED_FILES.txt")
    add_check(
        "learning_r24_migration_identity_ordering",
        'existing_revision > MANIFEST["package_revision"]' in learning_r21_migration_r24
        and '("learning_platform", "0007_r21_runtime_validation_fixes")' in release_identity_migration_r24
        and "finalize_release_identity" in release_identity_migration_r24
        and "MigrationIdentityOrderingFixContractTests" in release_identity_contract_r24,
        "R24 must prevent historical migration side effects from downgrading release identity during test database creation.",
        path="core/migrations/0013_r24_migration_identity_ordering_fix.py",
    )

    # R25 core test stability and legacy contract fix.
    core_tests_r25 = require_file("core/tests_system_updates.py")
    learning_r14_contract_r25 = require_file("core/test_update131_7_r14_learning_platform_content_management_contract.py")
    release_identity_migration_r25 = require_file("core/migrations/0013_r24_migration_identity_ordering_fix.py")
    core_test_contract_r25 = require_file("core/test_update131_7_r25_core_test_stability_legacy_contract.py")
    require_file("INSTALL_OPAL_UPDATE_131_7_R25_CORE_TEST_STABILITY_LEGACY_CONTRACT_FIX_AR.md")
    require_file("OPAL_UPDATE_131_7_R25_CORE_TEST_STABILITY_LEGACY_CONTRACT_FIX_RELEASE_NOTES_AR.md")
    require_file("OPAL_UPDATE_131_7_R25_VALIDATION_REPORT_AR.md")
    require_file("OPAL_UPDATE_131_7_R25_CHANGED_FILES.txt")
    add_check(
        "learning_r25_core_test_stability",
        "TemporaryDirectory(ignore_cleanup_errors=True)" in core_tests_r25
        and 'self.assertIn("0001_initial.py", migration_names)' in learning_r14_contract_r25
        and 'existing_revision > MANIFEST["package_revision"]' in release_identity_migration_r25
        and "CoreTestStabilityLegacyContractTests" in core_test_contract_r25,
        "R25 must stabilize filesystem-heavy core tests and replace stale migration-count assumptions.",
        path="core/tests_system_updates.py",
    )

    # R26 core snapshot test isolation.
    core_tests_r26 = require_file("core/tests_system_updates.py")
    low_memory_settings_r26 = require_file("config/settings_test_low_memory.py")
    core_snapshot_contract_r26 = require_file("core/test_update131_7_r26_core_snapshot_test_isolation_contract.py")
    require_file("INSTALL_OPAL_UPDATE_131_7_R26_CORE_SNAPSHOT_TEST_ISOLATION_FIX_AR.md")
    require_file("OPAL_UPDATE_131_7_R26_CORE_SNAPSHOT_TEST_ISOLATION_FIX_RELEASE_NOTES_AR.md")
    require_file("OPAL_UPDATE_131_7_R26_VALIDATION_REPORT_AR.md")
    require_file("OPAL_UPDATE_131_7_R26_CHANGED_FILES.txt")
    add_check(
        "learning_r26_core_snapshot_test_isolation",
        core_tests_r26.count('"core.update_engine_runtime.connections.close_all"') >= 3
        and "class DisableMigrations(dict):" in low_memory_settings_r26
        and "/tmp/opal_r26_low_memory_test.sqlite3" in low_memory_settings_r26
        and "CoreSnapshotTestIsolationContractTests" in core_snapshot_contract_r26,
        "R26 must isolate SQLite safety-snapshot tests from the shared Django test connection and ship low-memory test settings.",
        path="core/tests_system_updates.py",
    )

    result = {
        "update": f"OPAL Update {UPDATE}",
        "root": str(root),
        "ok": not errors,
        "summary": {
            "checks": len(checks),
            "passed": sum(1 for item in checks if item["ok"]),
            "failed": len(errors),
            "warnings": len(warnings),
            "python_files_parsed": len(python_files),
        },
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "scope_note": "Static source validation only; run Django checks, migrations, and tests in the project virtual environment.",
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        state = "PASS" if result["ok"] else "FAIL"
        print(f"[{state}] OPAL Update {UPDATE} static source gate")
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
        for item in errors:
            print(f"ERROR {item['code']}: {item['message']} ({item.get('path', '')})")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
