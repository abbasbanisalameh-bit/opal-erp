import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Count

from academics.models import Enrollment, Grade, Section, Subject
from accounting.models import StudentInvoice
from admissions.models import GradeFee
from attendance_v2.models import Attendance
from core.models import AcademicYear, School, Semester
from documents.models import IssuedDocument
from exams.models import Exam
from students.models import Student
from teachers.models import TeacherAssignment
from timetable.models import TimetableEntry


def _opal_release_version(root: Path) -> str:
    """Read the canonical code release marker without touching the database."""
    marker = root / "OPAL_VERSION.txt"
    try:
        value = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
    return value or "unknown"


class Command(BaseCommand):
    help = "فحص الجاهزية التشغيلية والأمنية لنواة OPAL ERP قبل الاعتماد."

    def add_arguments(self, parser):
        parser.add_argument(
            "--allow-empty",
            action="store_true",
            help="تحويل متطلبات البيانات والإعدادات الأولية إلى تحذيرات عند فحص نسخة جديدة.",
        )
        parser.add_argument(
            "--strict-warnings",
            action="store_true",
            help="اعتبار التحذيرات مانعة للاعتماد.",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="صيغة تقرير الجاهزية.",
        )
        parser.add_argument(
            "--output",
            help="مسار اختياري لحفظ نسخة JSON من تقرير الجاهزية دون تعديل البيانات.",
        )

    def handle(self, *args, **options):
        errors = []
        warnings = []
        allow_empty = options["allow_empty"]

        def add(target, code, message):
            target.append({"code": code, "message": message})

        def required(code, message):
            add(warnings if allow_empty else errors, code, message)

        # Deployment configuration gate.
        if settings.DEBUG:
            required("SEC_DEBUG", "وضع DEBUG مفعّل ويجب إيقافه في التشغيل الفعلي.")
        secret = str(settings.SECRET_KEY or "")
        if not secret or secret.startswith("django-insecure-") or secret == "django-insecure-change-this-key-before-production":
            required("SEC_SECRET_KEY", "مفتاح OPAL_SECRET_KEY غير مضبوط بمفتاح إنتاجي آمن.")
        allowed_hosts = list(getattr(settings, "ALLOWED_HOSTS", []) or [])
        if not allowed_hosts or "*" in allowed_hosts:
            required("SEC_ALLOWED_HOSTS", "ALLOWED_HOSTS فارغ أو يسمح لجميع النطاقات؛ يجب حصر نطاقات الموقع الفعلية.")
        if not getattr(settings, "SESSION_COOKIE_SECURE", False):
            add(warnings, "SEC_SESSION_COOKIE", "ملف جلسة المستخدم غير مقيد باتصال HTTPS.")
        if not getattr(settings, "CSRF_COOKIE_SECURE", False):
            add(warnings, "SEC_CSRF_COOKIE", "ملف CSRF غير مقيد باتصال HTTPS.")
        if not getattr(settings, "SECURE_SSL_REDIRECT", False):
            add(warnings, "SEC_SSL_REDIRECT", "تحويل HTTP إلى HTTPS غير مفعّل من إعدادات Django؛ تحقق أن المنصة تفرضه.")
        if not getattr(settings, "SECURE_HSTS_SECONDS", 0):
            add(warnings, "SEC_HSTS", "HSTS غير مفعّل؛ فعّله بعد التأكد النهائي من عمل HTTPS على النطاق.")

        executor = MigrationExecutor(connection)
        pending_plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if pending_plan:
            add(errors, "DB_PENDING_MIGRATIONS", f"يوجد {len(pending_plan)} ترحيلًا غير مطبق.")
        table_names = set(connection.introspection.table_names())
        if "curriculum_curriculum" in table_names:
            add(errors, "DB_PARALLEL_CURRICULUM", "ما زال جدول الخطة الموازي curriculum_curriculum موجودًا بعد تحديث الدمج.")

        if not get_user_model().objects.filter(is_active=True, is_superuser=True).exists():
            required("AUTH_SUPERUSER", "لا يوجد حساب مدير نظام فعّال للاسترداد والإدارة العليا.")

        schools = School.objects.filter(is_active=True)
        if not schools.exists():
            required("CORE_SCHOOL", "لا توجد مدرسة فعّالة مضبوطة في قاعدة البيانات.")

        for school in schools:
            if not school.branches.filter(is_active=True).exists():
                required("CORE_BRANCH", f"المدرسة {school.name} لا تحتوي فرعًا فعّالًا.")
            current_years = school.academic_years.filter(is_current=True, is_closed=False)
            if current_years.count() != 1:
                required(
                    "CORE_CURRENT_YEAR",
                    f"المدرسة {school.name} يجب أن تحتوي عامًا واحدًا مفتوحًا ومفعّلًا؛ الموجود {current_years.count()}.",
                )
            current_year = current_years.first()
            if current_year:
                if not Grade.objects.filter(school=school, is_active=True).exists():
                    required("ACADEMIC_GRADES", f"لا توجد صفوف فعالة للمدرسة {school.name}.")
                if not Section.objects.filter(academic_year=current_year, is_active=True).exists():
                    required("ACADEMIC_SECTIONS", f"لا توجد شعب فعالة للعام {current_year.name}.")
                if not GradeFee.objects.filter(academic_year=current_year, is_active=True).exists():
                    required("FINANCE_GRADE_FEES", f"لم تُضبط رسوم الصفوف للعام {current_year.name}.")
                if not Subject.objects.filter(academic_year=current_year, grade__school=school, is_active=True).exists():
                    required("ACADEMIC_SUBJECTS", f"لا توجد مواد فعالة للمدرسة {school.name}.")
                if Enrollment.objects.filter(academic_year=current_year, status="active").exists():
                    if not TeacherAssignment.objects.filter(academic_year=current_year, is_active=True).exists():
                        add(warnings, "ACADEMIC_ASSIGNMENTS", f"لا توجد تكليفات تدريسية فعالة للعام {current_year.name}.")
                    if not TimetableEntry.objects.filter(academic_year=current_year, is_active=True).exists():
                        add(warnings, "ACADEMIC_TIMETABLE", f"لا توجد حصص فعالة في جدول العام {current_year.name}.")

        duplicated_current = (
            AcademicYear.objects.filter(is_current=True)
            .values("school_id")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
        )
        for row in duplicated_current:
            add(errors, "CORE_DUPLICATE_CURRENT_YEAR", f"المدرسة #{row['school_id']} لديها أكثر من عام دراسي حالي.")

        duplicated_semesters = (
            Semester.objects.filter(is_current=True)
            .values("academic_year_id")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
        )
        for row in duplicated_semesters:
            add(errors, "CORE_DUPLICATE_CURRENT_TERM", f"العام #{row['academic_year_id']} لديه أكثر من فصل دراسي حالي.")

        for year in AcademicYear.objects.select_related("school").prefetch_related("semesters"):
            codes = set(year.semesters.values_list("code", flat=True))
            if year.semesters.count() != 2 or codes != {"first", "second"}:
                add(errors, "CORE_TWO_TERMS", f"العام {year.name} لا يحتوي الفصلين الرسميين فقط.")
            if year.is_closed and year.is_current:
                add(errors, "CORE_CLOSED_CURRENT_YEAR", f"العام المغلق {year.name} محدد كعام حالي.")
            if year.is_closed:
                active_enrollments = year.enrollments.filter(status="active").count()
                if active_enrollments:
                    add(errors, "CORE_CLOSED_ACTIVE_ENROLLMENTS", f"العام المغلق {year.name} يحتوي {active_enrollments} قيدًا نشطًا.")
                unfinished = year.exams.exclude(status="closed", is_locked=True).count()
                if unfinished:
                    add(errors, "CORE_CLOSED_UNFINISHED_EXAMS", f"العام المغلق {year.name} يحتوي {unfinished} امتحانًا غير مغلق.")
                active_assignments = TeacherAssignment.objects.filter(academic_year=year, is_active=True).count()
                if active_assignments:
                    add(errors, "CORE_CLOSED_ASSIGNMENTS", f"العام المغلق {year.name} يحتوي {active_assignments} تكليفًا فعالًا.")
                active_timetable = TimetableEntry.objects.filter(academic_year=year, is_active=True).count()
                if active_timetable:
                    add(errors, "CORE_CLOSED_TIMETABLE", f"العام المغلق {year.name} يحتوي {active_timetable} حصة فعالة.")
                active_sections = Section.objects.filter(academic_year=year, is_active=True).count()
                if active_sections:
                    add(errors, "CORE_CLOSED_SECTIONS", f"العام المغلق {year.name} يحتوي {active_sections} شعبة فعالة.")
                active_fees = GradeFee.objects.filter(academic_year=year, is_active=True).count()
                if active_fees:
                    add(errors, "CORE_CLOSED_GRADE_FEES", f"العام المغلق {year.name} يحتوي {active_fees} إعداد رسوم فعالًا.")
                active_subjects = Subject.objects.filter(academic_year=year, is_active=True).count()
                if active_subjects:
                    add(errors, "CORE_CLOSED_SUBJECT_PLANS", f"العام المغلق {year.name} يحتوي {active_subjects} مادة خطة فعالة.")
                unlocked_attendance = Attendance.objects.filter(academic_year=year, is_locked=False).count()
                if unlocked_attendance:
                    add(errors, "CORE_CLOSED_ATTENDANCE", f"العام المغلق {year.name} يحتوي {unlocked_attendance} سجل حضور غير مقفل.")

        for semester in Semester.objects.select_related("academic_year"):
            if semester.start_date < semester.academic_year.start_date or semester.end_date > semester.academic_year.end_date:
                add(errors, "CORE_TERM_DATES", f"الفصل #{semester.pk} يقع خارج حدود عامه الدراسي.")

        for section in Section.objects.select_related("academic_year", "grade", "branch__school"):
            if section.academic_year.school_id != section.branch.school_id:
                add(errors, "ACADEMIC_SECTION_YEAR", f"الشعبة #{section.pk} مرتبطة بعام لمدرسة أخرى.")
            if section.grade.school_id != section.branch.school_id:
                add(errors, "ACADEMIC_SECTION_GRADE", f"الشعبة #{section.pk} مرتبطة بصف لمدرسة أخرى.")
            active_count = section.active_enrollment_count
            if section.capacity and active_count > section.capacity:
                add(warnings, "ACADEMIC_SECTION_CAPACITY", f"الشعبة #{section.pk} تتجاوز سعتها ({active_count}/{section.capacity}).")
            if section.is_active and not section.capacity:
                add(warnings, "ACADEMIC_SECTION_NO_CAPACITY", f"الشعبة #{section.pk} فعالة دون سعة محددة.")
            if section.is_active and not section.homeroom_teacher_id:
                add(warnings, "ACADEMIC_SECTION_NO_HOMEROOM", f"الشعبة #{section.pk} دون مربي صف.")

        for subject in Subject.objects.select_related("academic_year", "grade"):
            if subject.academic_year.school_id != subject.grade.school_id:
                add(errors, "ACADEMIC_SUBJECT_SCHOOL", f"المادة #{subject.pk} تربط عامًا وصفًا من مدرستين مختلفتين.")
            if not 1 <= subject.weekly_periods <= 20:
                add(errors, "ACADEMIC_SUBJECT_PERIODS", f"المادة #{subject.pk} تحمل عدد حصص غير صالح.")
            if not subject.canonical_key or not subject.color:
                add(errors, "ACADEMIC_SUBJECT_IDENTITY", f"المادة #{subject.pk} لا تحمل هوية ولونًا موحدين.")

        for assignment in TeacherAssignment.objects.select_related("academic_year", "section", "subject"):
            if assignment.subject.academic_year_id != assignment.academic_year_id:
                add(errors, "ACADEMIC_ASSIGNMENT_SUBJECT_YEAR", f"التكليف #{assignment.pk} يستخدم مادة من عام آخر.")
            if assignment.subject.grade_id != assignment.section.grade_id:
                add(errors, "ACADEMIC_ASSIGNMENT_SUBJECT_GRADE", f"التكليف #{assignment.pk} يستخدم مادة من صف آخر.")

        for entry in TimetableEntry.objects.select_related("academic_year", "section", "subject"):
            if entry.subject.academic_year_id != entry.academic_year_id:
                add(errors, "ACADEMIC_TIMETABLE_SUBJECT_YEAR", f"الحصة #{entry.pk} تستخدم مادة من عام آخر.")
            if entry.subject.grade_id != entry.section.grade_id:
                add(errors, "ACADEMIC_TIMETABLE_SUBJECT_GRADE", f"الحصة #{entry.pk} تستخدم مادة من صف آخر.")

        duplicate_active_enrollments = (
            Enrollment.objects.filter(status="active")
            .values("student_id")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
        )
        for row in duplicate_active_enrollments:
            add(errors, "ACADEMIC_MULTIPLE_ACTIVE_ENROLLMENTS", f"الطالب #{row['student_id']} لديه {row['total']} قيود نشطة.")

        for enrollment in Enrollment.objects.select_related("student", "academic_year", "grade", "section"):
            if enrollment.section_id:
                if enrollment.section.grade_id != enrollment.grade_id:
                    add(errors, "ACADEMIC_ENROLLMENT_GRADE", f"القيد #{enrollment.pk} في شعبة لا تتبع صفه.")
                if enrollment.section.academic_year_id != enrollment.academic_year_id:
                    add(errors, "ACADEMIC_ENROLLMENT_YEAR", f"القيد #{enrollment.pk} في شعبة لا تتبع عامه.")
            if enrollment.status == "active" and (not enrollment.student.is_active or enrollment.student.status != "active"):
                add(errors, "ACADEMIC_STUDENT_STATUS", f"القيد #{enrollment.pk} نشط بينما حالة الطالب غير نشطة.")

        for invoice in StudentInvoice.objects.prefetch_related("payments"):
            if invoice.status == "cancelled" and invoice.payments.filter(status="posted").exists():
                add(errors, "FINANCE_CANCELLED_WITH_PAYMENT", f"الرسوم {invoice.invoice_number} ملغاة ولها دفعات مرحلة.")
            if invoice.total_paid > invoice.net_amount:
                add(errors, "FINANCE_OVERPAYMENT", f"الرسوم {invoice.invoice_number} مدفوعة بأكثر من صافي قيمتها.")

        for exam in Exam.objects.select_related("academic_year", "semester"):
            if exam.status in ["approved", "published", "closed"] and not exam.is_locked:
                add(errors, "EXAMS_UNLOCKED_FINAL", f"الامتحان #{exam.pk} حالته {exam.status} لكنه غير مقفل.")
            if exam.semester.academic_year_id != exam.academic_year_id:
                add(errors, "EXAMS_TERM_YEAR", f"الامتحان #{exam.pk} مرتبط بفصل لا يتبع عامه.")

        for document in IssuedDocument.objects.filter(status="cancelled"):
            if not document.cancelled_at or not document.cancellation_reason.strip():
                add(errors, "DOCUMENTS_INVALID_CANCELLATION", f"الوثيقة {document.document_number} ملغاة دون بيانات مكتملة.")

        slots = defaultdict(list)
        for entry in TimetableEntry.objects.filter(is_active=True).values(
            "pk", "academic_year_id", "day", "time_slot_id", "section_id", "teacher_id", "room"
        ):
            slots[(entry["academic_year_id"], entry["day"], entry["time_slot_id"])].append(entry)
        for entries in slots.values():
            for field, label in (("section_id", "الشعبة"), ("teacher_id", "المعلم"), ("room", "الغرفة")):
                seen = {}
                for entry in entries:
                    value = entry[field]
                    if value in (None, ""):
                        continue
                    if value in seen:
                        add(errors, "TIMETABLE_COLLISION", f"تعارض في {label} بين الحصتين #{seen[value]} و#{entry['pk']}.")
                    else:
                        seen[value] = entry["pk"]

        demo_students = Student.objects.filter(is_demo=True).count()
        if demo_students:
            add(warnings, "DATA_GENERATED_STUDENTS", f"توجد سجلات مولدة آليًا وفق الحقل التاريخي لعدد {demo_students} طالب.")

        # سلامة ملفات التشغيل والمجلدات الأساسية. هذا فحص قراءة فقط.
        root = Path(settings.BASE_DIR)
        required_files = (
            "manage.py",
            "templates/includes/sidebar.html",
            "templates/includes/topbar.html",
            "static/css/opal_erp.css",
            "docs/uiux/OPAL_UI_UX_GUIDE_AR.md",
        )
        missing_files = [item for item in required_files if not (root / item).is_file()]
        if missing_files:
            add(errors, "APP_REQUIRED_FILES", "ملفات OPAL الأساسية مفقودة: " + ", ".join(missing_files))

        # بوابة Update 122: عقود قشرة التشغيل والتنقل المركزي. قراءة فقط.
        from core.runtime_contracts import run_runtime_stability_audit

        runtime_report = run_runtime_stability_audit(root=root)
        for issue in runtime_report["issues"]:
            add(
                errors,
                f"APP_{issue['code'].upper()}",
                issue["message"] + (f" ({issue['path']})" if issue.get("path") else ""),
            )

        # بوابة Update 124: المسارات الحرجة وبيانات دورة الخدمة. قراءة فقط.
        from core.critical_workflow_contracts import (
            audit_critical_workflow_data,
            run_critical_workflow_contract_audit,
        )

        critical_contracts = run_critical_workflow_contract_audit(root=root)
        for issue in critical_contracts["issues"]:
            add(
                errors,
                f"APP_{issue['code'].upper()}",
                issue["message"] + (f" ({issue['path']})" if issue.get("path") else ""),
            )
        critical_data = audit_critical_workflow_data()
        for issue in critical_data["errors"]:
            add(errors, issue["code"], issue["message"])
        for issue in critical_data["warnings"]:
            add(warnings, issue["code"], issue["message"])

        # بوابة Update 125: مدخل مرئي واحد لكل وظيفة ولكل دور. قراءة فقط.
        from core.single_entry_contracts import run_single_entry_contract_audit

        single_entry = run_single_entry_contract_audit(root=root)
        for issue in single_entry["issues"]:
            add(
                errors,
                f"APP_{issue['code'].upper()}",
                issue["message"] + (f" ({issue['path']})" if issue.get("path") else ""),
            )

        # بوابة Update 126: لغة الرسوم المدرسية المبسطة وروابط المؤشرات الرسمية. قراءة فقط.
        from core.school_finance_language_contracts import run_school_finance_language_audit

        finance_language = run_school_finance_language_audit(root=root)
        for issue in finance_language["issues"]:
            add(
                errors,
                f"APP_{issue['code'].upper()}",
                issue["message"] + (f" ({issue['path']})" if issue.get("path") else ""),
            )

        # بوابة Update 127: الخطة والتكليفات والنصاب والاستراحات ضمن محرك واحد بلا نظام موازٍ.
        from core.smart_timetable_contracts import run_smart_timetable_contract_audit

        smart_timetable = run_smart_timetable_contract_audit(root=root)
        for issue in smart_timetable["issues"]:
            add(
                errors,
                f"APP_{issue['code'].upper()}",
                issue["message"] + (f" ({issue['path']})" if issue.get("path") else ""),
            )

        for path, code, label in (
            (Path(settings.MEDIA_ROOT), "FS_MEDIA", "مجلد الوسائط"),
            (Path(settings.STATIC_ROOT), "FS_STATIC_ROOT", "مجلد static المجمّع"),
        ):
            if not path.exists():
                add(warnings, code, f"{label} غير موجود بعد: {path}")
            elif not os.access(path, os.W_OK):
                add(errors, code, f"{label} غير قابل للكتابة: {path}")

        report = {
            "audit": "OPAL ERP canonical production readiness",
            "version": _opal_release_version(root),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ready": not errors and (not warnings or not options["strict_warnings"]),
            "errors": errors,
            "warnings": warnings,
            "summary": {"errors": len(errors), "warnings": len(warnings)},
            "safety": {
                "data_deleted": False,
                "database_modified": False,
                "student_model": "students.Student",
            },
        }

        output_path = options.get("output")
        if output_path:
            output = Path(output_path)
            if not output.is_absolute():
                output = root / output
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if options["format"] == "json":
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self.stdout.write(self.style.MIGRATE_HEADING("OPAL ERP — تقرير الجاهزية النهائي"))
            for item in warnings:
                self.stdout.write(self.style.WARNING(f"تحذير [{item['code']}]: {item['message']}"))
            for item in errors:
                self.stdout.write(self.style.ERROR(f"خطأ [{item['code']}]: {item['message']}"))
            self.stdout.write(
                f"الملخص: أخطاء حرجة {len(errors)} | تحذيرات {len(warnings)} | "
                f"الحالة {'جاهز' if report['ready'] else 'غير جاهز'}"
            )

        if errors:
            raise CommandError(f"فشل فحص الجاهزية: {len(errors)} مشكلة حرجة.")
        if options["strict_warnings"] and warnings:
            raise CommandError(f"فشل الفحص الصارم: {len(warnings)} تحذيرًا.")
        if options["format"] == "text":
            self.stdout.write(self.style.SUCCESS("نجح فحص الجاهزية دون أخطاء حرجة."))
