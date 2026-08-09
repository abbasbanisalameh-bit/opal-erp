from __future__ import annotations

import hashlib
import json
from collections import OrderedDict

from django.apps import apps
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core import signing
from django.core.management.color import no_style
from django.db import connection, transaction
from django.utils import timezone

from .models import ProductionDataResetRun


PRODUCTION_RESET_CONFIRMATION = "تهيئة التشغيل الفعلي"
PREVIEW_TOKEN_SALT = "opal.production-data-reset.preview.v1"
PREVIEW_TOKEN_MAX_AGE_SECONDS = 30 * 60


# Ordered from dependent/leaf records to their protected parents.  The school,
# branches and configuration rows are intentionally absent from this list.
DELETE_MODEL_LABELS = (
    # Learning platform transactions, identities and content.
    "learning_platform.LearningStudentAccessOverride",
    "learning_platform.LearningGradeAccessOverride",
    "learning_platform.LearningStudentProfile",
    "learning_platform.LearningTeacherProfile",
    "learning_platform.LearningPaymentEvent",
    "learning_platform.LearningAPIToken",
    "learning_platform.LearningRateLimitBucket",
    "learning_platform.LearningEmailVerificationRequest",
    "learning_platform.LearningPasswordResetRequest",
    "learning_platform.LearningNotification",
    "learning_platform.LearningAIDraft",
    "learning_platform.LearningAIInteraction",
    "learning_platform.LearningAuditEvent",
    "learning_platform.LearningCertificate",
    "learning_platform.LearningSubmission",
    "learning_platform.LearningQuestion",
    "learning_platform.LearningAssessment",
    "learning_platform.LearningLessonProgress",
    "learning_platform.LearningEnrollment",
    "learning_platform.LearningPaymentOrder",
    "learning_platform.LearningSubscriptionCard",
    "learning_platform.LearningSubscriptionPlan",
    "learning_platform.LearningLesson",
    "learning_platform.LearningCourse",
    "learning_platform.LearningSubject",
    "learning_platform.LearningAccount",

    # Finance and admission chains.
    "accounting.MonthlyFinancialStatement",
    "accounting.CanteenTransaction",
    "accounting.FinancialCarryForward",
    "accounting.FinancialYearClosure",
    "accounting.Receipt",
    "admissions.FeePaymentAllocation",
    "admissions.FeePayment",
    "accounting.DiscountRequest",
    "accounting.Installment",
    "accounting.StudentPayment",
    "admissions.StudentRegistration",
    "accounting.StudentInvoice",
    "accounting.FeeCategory",
    "accounting.ExpenseEntry",
    "accounting.MonthlyFinancialTarget",

    # Issued documents only; document templates/settings survive.
    "documents.StudentIssuedDocument",
    "documents.IssuedDocument",

    # Results, attendance and timetable operations.
    "exams.AnnualStudentResult",
    "exams.AnnualSubjectResult",
    "exams.SemesterSubjectResult",
    "exams.StudentMark",
    "exams.Exam",
    "exams.ExamCycle",
    "attendance_v2.AttendanceRegister",
    "attendance_v2.Attendance",
    "timetable.BiometricDailySummary",
    "timetable.TeacherBiometricPunch",
    "timetable.TeacherBiometricIdentity",
    "timetable.ClassCoverage",
    "timetable.TeacherAbsence",
    "timetable.TimetableEntry",
    "timetable.SchoolDayEvent",
    "timetable.TimeSlot",

    # Teacher and family operations.
    "teachers.Homework",
    "teachers.TeacherPerformanceSnapshot",
    "teachers.TeacherPayroll",
    "teachers.TeacherAdvance",
    "parent_portal.TeacherMonthlyEvaluation",
    "teachers.TeacherAssignment",
    "teachers.TeacherDocument",
    "teachers.Teacher",
    "parent_portal.FamilyStudent",
    "parent_portal.Family",

    # Student lifecycle and academic structure.
    "academics.StudentLifecycleEvent",
    "academics.StudentDocument",
    "academics.Enrollment",
    "students.Student",
    "admissions.GradeFee",
    "admissions.TransportRoute",
    "academics.Section",
    "academics.Subject",
    "academics.Grade",
    "core.SemesterStructureSnapshot",
    "core.Semester",
    "core.AcademicYear",

    # General operations, communications and generated reporting data.
    "enterprise_ops.ApprovalAction",
    "enterprise_ops.MonthlyServiceEvaluation",
    "enterprise_ops.FeedbackTicket",
    "enterprise_ops.BroadcastMessage",
    "enterprise_ops.WorkflowRequest",
    "enterprise_ops.Notification",
    "enterprise_ops.ReportPreset",
    "announcements.Announcement",
    "openemis_integration.OpenEMISSyncLog",
    "core.DataIntegrityIssue",
    "core.DataIntegrityRun",
    "core.AuditLog",
    "core.Sequence",
)


CATEGORY_MODEL_LABELS = OrderedDict(
    [
        ("students", ("students.Student", "academics.Enrollment", "academics.StudentLifecycleEvent", "academics.StudentDocument")),
        ("guardians", ("parent_portal.Family", "parent_portal.FamilyStudent")),
        ("teachers", ("teachers.Teacher", "teachers.TeacherAssignment", "teachers.Homework", "teachers.TeacherDocument", "teachers.TeacherAdvance", "teachers.TeacherPayroll", "teachers.TeacherPerformanceSnapshot", "parent_portal.TeacherMonthlyEvaluation")),
        ("admissions", ("admissions.StudentRegistration", "admissions.FeePayment", "admissions.FeePaymentAllocation", "admissions.GradeFee", "admissions.TransportRoute")),
        ("finance", ("accounting.StudentInvoice", "accounting.StudentPayment", "accounting.Receipt", "accounting.Installment", "accounting.DiscountRequest", "accounting.ExpenseEntry", "accounting.MonthlyFinancialTarget", "accounting.FinancialYearClosure", "accounting.FinancialCarryForward", "accounting.CanteenTransaction", "accounting.MonthlyFinancialStatement", "accounting.FeeCategory")),
        ("attendance", ("attendance_v2.Attendance", "attendance_v2.AttendanceRegister")),
        ("timetable", ("timetable.TimeSlot", "timetable.TimetableEntry", "timetable.SchoolDayEvent", "timetable.TeacherAbsence", "timetable.ClassCoverage")),
        ("exams", ("exams.ExamCycle", "exams.Exam", "exams.StudentMark", "exams.SemesterSubjectResult", "exams.AnnualSubjectResult", "exams.AnnualStudentResult")),
        ("documents", ("documents.IssuedDocument", "documents.StudentIssuedDocument")),
        ("announcements", ("announcements.Announcement",)),
        ("academic_structure", ("core.AcademicYear", "core.Semester", "core.SemesterStructureSnapshot", "academics.Grade", "academics.Section", "academics.Subject")),
        ("learning_platform", tuple(label for label in DELETE_MODEL_LABELS if label.startswith("learning_platform."))),
        ("enterprise_operations", tuple(label for label in DELETE_MODEL_LABELS if label.startswith("enterprise_ops."))),
        ("integration_logs", ("openemis_integration.OpenEMISSyncLog",)),
        ("audit_and_sequences", ("core.DataIntegrityIssue", "core.DataIntegrityRun", "core.AuditLog", "core.Sequence")),
    ]
)


PRESERVED_MODEL_LABELS = (
    "core.School",
    "core.Branch",
    "accounts.Role",
    "enterprise_ops.RolePermissionRule",
    "admissions.RegistrationSettings",
    "documents.DocumentTemplate",
    "documents.DocumentSettings",
    "timetable.SchoolScheduleSettings",
    "openemis_integration.OpenEMISSettings",
    "learning_platform.LearningAISettings",
    "learning_platform.LearningAccessSettings",
)


PRESERVED_LABELS_AR = {
    "core.School": "بيانات المدرسة وهويتها",
    "core.Branch": "الفروع",
    "accounts.Role": "الأدوار",
    "enterprise_ops.RolePermissionRule": "مصفوفة الصلاحيات",
    "admissions.RegistrationSettings": "إعدادات التسجيل والخصومات",
    "documents.DocumentTemplate": "قوالب الوثائق",
    "documents.DocumentSettings": "إعدادات الوثائق والتوقيع",
    "timetable.SchoolScheduleSettings": "إعدادات أيام الدوام",
    "openemis_integration.OpenEMISSettings": "إعدادات OpenEMIS",
    "learning_platform.LearningAISettings": "إعدادات مساعد منصة التعلم",
    "learning_platform.LearningAccessSettings": "إعدادات إتاحة منصة التعلم للمدرسة",
    "auth.User.current_manager": "حساب المدير الحالي",
    "development_center.total": "بيانات مركز التطوير",
}


CATEGORY_LABELS_AR = {
    "students": "الطلاب وملفاتهم الأكاديمية",
    "guardians": "أولياء الأمور وروابط الإخوة",
    "teachers": "المعلمون وسجلاتهم التشغيلية",
    "admissions": "التسجيل ورسوم الصفوف والمواصلات",
    "finance": "الفواتير والدفعات والإيصالات",
    "attendance": "الحضور والغياب",
    "timetable": "الجدول والحصص والغيابات والتغطيات",
    "exams": "الامتحانات والعلامات والنتائج",
    "documents": "الوثائق الصادرة",
    "announcements": "الإعلانات",
    "academic_structure": "الأعوام والصفوف والشعب والمواد",
    "learning_platform": "بيانات منصة التعلم",
    "enterprise_operations": "الطلبات والإشعارات والتقارير التشغيلية",
    "integration_logs": "سجلات OpenEMIS",
    "audit_and_sequences": "سجلات التدقيق والعدادات",
    "users": "حسابات المستخدمين غير حساب المدير",
    "sessions": "جلسات المستخدمين القديمة",
}


def _model(label):
    app_label, model_name = label.split(".", 1)
    return apps.get_model(app_label, model_name)


def _count_labels(labels):
    return {label: _model(label).objects.count() for label in labels}


def _category_counts(model_counts, *, user_count=0, session_count=0):
    result = OrderedDict()
    for category, labels in CATEGORY_MODEL_LABELS.items():
        result[category] = sum(model_counts.get(label, 0) for label in labels)
    result["users"] = user_count
    result["sessions"] = session_count
    return result


def _preserved_summary(keep_user):
    summary = OrderedDict()
    for label in PRESERVED_MODEL_LABELS:
        model = _model(label)
        summary[label] = model.objects.count()
    summary["auth.User.current_manager"] = 1 if User.objects.filter(pk=keep_user.pk, is_superuser=True).exists() else 0
    summary["development_center.total"] = sum(
        model.objects.count()
        for model in apps.get_app_config("development_center").get_models()
    )
    return summary


def _snapshot_digest(model_counts, *, user_count, session_count, keep_user_id):
    payload = {
        "models": model_counts,
        "users": user_count,
        "sessions": session_count,
        "keep_user_id": keep_user_id,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def collect_production_reset_preview(*, keep_user, current_session_key=None):
    if keep_user is None or not keep_user.pk or not keep_user.is_superuser:
        raise ValueError("تهيئة التشغيل الفعلي متاحة لمدير النظام الأعلى فقط.")

    model_counts = _count_labels(DELETE_MODEL_LABELS)
    user_count = User.objects.exclude(pk=keep_user.pk).count()
    sessions = Session.objects.all()
    if current_session_key:
        sessions = sessions.exclude(session_key=current_session_key)
    session_count = sessions.count()
    digest = _snapshot_digest(
        model_counts,
        user_count=user_count,
        session_count=session_count,
        keep_user_id=keep_user.pk,
    )
    token = signing.dumps(
        {"user_id": keep_user.pk, "digest": digest},
        salt=PREVIEW_TOKEN_SALT,
        compress=True,
    )
    category_counts = _category_counts(model_counts, user_count=user_count, session_count=session_count)
    preserved = _preserved_summary(keep_user)
    return {
        "model_counts": model_counts,
        "category_counts": category_counts,
        "category_rows": [
            {"key": key, "label": CATEGORY_LABELS_AR.get(key, key), "count": value}
            for key, value in category_counts.items()
        ],
        "preserved": preserved,
        "preserved_rows": [
            {"key": key, "label": PRESERVED_LABELS_AR.get(key, key), "count": value}
            for key, value in preserved.items()
        ],
        "preview_token": token,
        "digest": digest,
        "total_records": sum(model_counts.values()) + user_count + session_count,
    }


def _validate_preview_token(*, token, keep_user, current_preview):
    try:
        payload = signing.loads(
            token,
            salt=PREVIEW_TOKEN_SALT,
            max_age=PREVIEW_TOKEN_MAX_AGE_SECONDS,
        )
    except signing.BadSignature as exc:
        raise ValueError("انتهت صلاحية المعاينة أو تغيرت. حدّث الصفحة وراجع الأعداد من جديد.") from exc
    if payload.get("user_id") != keep_user.pk:
        raise ValueError("المعاينة لا تخص حساب المدير الحالي.")
    if payload.get("digest") != current_preview["digest"]:
        raise ValueError("تغيرت البيانات بعد المعاينة. حدّث الصفحة قبل التنفيذ.")


def _reset_database_sequences(models_to_reset):
    sql_statements = connection.ops.sequence_reset_sql(no_style(), models_to_reset)
    if not sql_statements:
        return
    with connection.cursor() as cursor:
        for sql in sql_statements:
            cursor.execute(sql)


def _delete_model_rows(label):
    model = _model(label)
    count = model.objects.count()
    if count:
        model.objects.all().delete()
    return count, model


def execute_production_data_reset(*, keep_user, preview_token, current_session_key=None):
    if keep_user is None or not keep_user.pk or not keep_user.is_superuser:
        raise ValueError("تهيئة التشغيل الفعلي متاحة لمدير النظام الأعلى فقط.")

    current_preview = collect_production_reset_preview(
        keep_user=keep_user,
        current_session_key=current_session_key,
    )
    _validate_preview_token(token=preview_token, keep_user=keep_user, current_preview=current_preview)

    running_exists = ProductionDataResetRun.objects.filter(
        status=ProductionDataResetRun.Status.RUNNING,
    ).exists()
    if running_exists:
        raise ValueError("توجد عملية تهيئة أخرى قيد التنفيذ. انتظر حتى تنتهي.")

    run = ProductionDataResetRun.objects.create(
        requested_by=keep_user,
        status=ProductionDataResetRun.Status.RUNNING,
        preview_counts=current_preview["category_counts"],
        preserved_summary=current_preview["preserved"],
        started_at=timezone.now(),
    )

    deleted_model_counts = OrderedDict()
    deleted_models = []
    try:
        with transaction.atomic():
            locked_user = User.objects.select_for_update().get(pk=keep_user.pk)
            if not locked_user.is_superuser:
                raise ValueError("فقد الحساب صلاحية مدير النظام الأعلى قبل التنفيذ.")

            # Break the historical self-PROTECT edge before deleting academic years.
            academic_year = _model("core.AcademicYear")
            academic_year.objects.exclude(preparation_source=None).update(preparation_source=None)

            for label in DELETE_MODEL_LABELS:
                count, model = _delete_model_rows(label)
                deleted_model_counts[label] = count
                deleted_models.append(model)

            removable_users = User.objects.exclude(pk=locked_user.pk)
            deleted_users = removable_users.count()
            removable_users.delete()

            sessions = Session.objects.all()
            if current_session_key:
                sessions = sessions.exclude(session_key=current_session_key)
            deleted_sessions = sessions.count()
            sessions.delete()

            _reset_database_sequences(deleted_models)

            remaining_model_counts = _count_labels(DELETE_MODEL_LABELS)
            if any(remaining_model_counts.values()):
                nonzero = {key: value for key, value in remaining_model_counts.items() if value}
                raise RuntimeError(f"بقيت سجلات تشغيلية بعد التهيئة: {nonzero}")
            if User.objects.exclude(pk=locked_user.pk).exists():
                raise RuntimeError("بقيت حسابات مستخدمين غير حساب المدير الحالي.")
            if not User.objects.filter(pk=locked_user.pk, is_superuser=True).exists():
                raise RuntimeError("تعذر التحقق من بقاء حساب المدير الأعلى.")

            preserved_after = _preserved_summary(locked_user)
            for label, before_count in current_preview["preserved"].items():
                if preserved_after.get(label) != before_count:
                    raise RuntimeError(f"تغير سجل محفوظ أثناء التهيئة: {label}")

        deleted_category_counts = _category_counts(
            deleted_model_counts,
            user_count=deleted_users,
            session_count=deleted_sessions,
        )
        remaining_category_counts = _category_counts(
            _count_labels(DELETE_MODEL_LABELS),
            user_count=User.objects.exclude(pk=keep_user.pk).count(),
            session_count=(Session.objects.exclude(session_key=current_session_key).count() if current_session_key else Session.objects.count()),
        )
        run.status = ProductionDataResetRun.Status.SUCCEEDED
        run.deleted_counts = deleted_category_counts
        run.remaining_counts = remaining_category_counts
        run.preserved_summary = _preserved_summary(keep_user)
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "deleted_counts", "remaining_counts", "preserved_summary", "finished_at"])
        return run
    except Exception as exc:
        run.status = ProductionDataResetRun.Status.FAILED
        run.error_message = str(exc)[:4000]
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error_message", "finished_at"])
        raise
