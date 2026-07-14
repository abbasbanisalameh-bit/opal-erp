from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from academics.models import Enrollment, Section
from accounting.models import StudentInvoice
from core.models import AcademicYear, School, Semester
from documents.models import IssuedDocument
from exams.models import Exam
from timetable.models import TimetableEntry


class Command(BaseCommand):
    help = "فحص اتساق النواة التشغيلية لنظام OPAL ERP قبل الاعتماد."

    def add_arguments(self, parser):
        parser.add_argument(
            "--allow-empty",
            action="store_true",
            help="السماح بقاعدة بيانات خالية عند فحص نسخة جديدة.",
        )

    def handle(self, *args, **options):
        errors = []
        warnings = []

        if not School.objects.exists():
            message = "لا توجد مدرسة مضبوطة في قاعدة البيانات."
            (warnings if options["allow_empty"] else errors).append(message)

        duplicated_current = (
            AcademicYear.objects.filter(is_current=True)
            .values("school_id")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
        )
        for row in duplicated_current:
            errors.append(f"المدرسة #{row['school_id']} لديها أكثر من عام دراسي حالي.")

        duplicated_semesters = (
            Semester.objects.filter(is_current=True)
            .values("academic_year_id")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
        )
        for row in duplicated_semesters:
            errors.append(f"العام الدراسي #{row['academic_year_id']} لديه أكثر من فصل دراسي حالي.")

        for semester in Semester.objects.select_related("academic_year"):
            if semester.start_date < semester.academic_year.start_date or semester.end_date > semester.academic_year.end_date:
                errors.append(f"الفصل الدراسي #{semester.pk} يقع خارج حدود عامه الدراسي.")

        for section in Section.objects.select_related("academic_year", "grade", "branch__school"):
            if section.academic_year_id and section.academic_year.school_id != section.branch.school_id:
                errors.append(f"الشعبة #{section.pk} مرتبطة بعام دراسي لمدرسة أخرى.")
            if section.grade_id and section.grade.school_id != section.branch.school_id:
                errors.append(f"الشعبة #{section.pk} مرتبطة بصف لمدرسة أخرى.")
            if section.capacity and section.active_enrollment_count > section.capacity:
                warnings.append(f"الشعبة #{section.pk} تتجاوز سعتها ({section.active_enrollment_count}/{section.capacity}).")

        for enrollment in Enrollment.objects.select_related("academic_year", "grade", "section"):
            if enrollment.section_id:
                if enrollment.section.grade_id != enrollment.grade_id:
                    errors.append(f"قيد الطالب #{enrollment.pk} في شعبة لا تتبع صفه.")
                if enrollment.section.academic_year_id and enrollment.section.academic_year_id != enrollment.academic_year_id:
                    errors.append(f"قيد الطالب #{enrollment.pk} في شعبة لا تتبع عامه الدراسي.")

        for invoice in StudentInvoice.objects.prefetch_related("payments"):
            if invoice.status == "cancelled" and invoice.payments.filter(status="posted").exists():
                errors.append(f"الرسوم {invoice.invoice_number} ملغاة ولها دفعات مرحلة.")
            if invoice.total_paid > invoice.net_amount:
                errors.append(f"الرسوم {invoice.invoice_number} مدفوعة بأكثر من صافي قيمتها.")

        for exam in Exam.objects.select_related("academic_year", "semester"):
            if exam.status in ["approved", "published", "closed"] and not exam.is_locked:
                errors.append(f"الامتحان #{exam.pk} حالته {exam.status} لكنه غير مقفل.")
            if exam.semester_id and exam.semester.academic_year_id != exam.academic_year_id:
                errors.append(f"الامتحان #{exam.pk} مرتبط بفصل لا يتبع عامه الدراسي.")

        for document in IssuedDocument.objects.filter(status="cancelled"):
            if not document.cancelled_at or not document.cancellation_reason.strip():
                errors.append(f"الوثيقة {document.document_number} ملغاة دون بيانات إلغاء مكتملة.")

        slots = defaultdict(list)
        for entry in TimetableEntry.objects.filter(is_active=True).values(
            "pk", "academic_year_id", "day", "time_slot_id", "section_id", "teacher_id", "room"
        ):
            key = (entry["academic_year_id"], entry["day"], entry["time_slot_id"])
            slots[key].append(entry)
        for entries in slots.values():
            for field, label in (("section_id", "الشعبة"), ("teacher_id", "المعلم"), ("room", "الغرفة")):
                seen = {}
                for entry in entries:
                    value = entry[field]
                    if value in (None, ""):
                        continue
                    if value in seen:
                        errors.append(f"تعارض جدول في {label} بين الحصتين #{seen[value]} و#{entry['pk']}.")
                    else:
                        seen[value] = entry["pk"]

        self.stdout.write(self.style.MIGRATE_HEADING("OPAL ERP — Core Readiness"))
        for warning in warnings:
            self.stdout.write(self.style.WARNING(f"تحذير: {warning}"))
        if errors:
            for error in errors:
                self.stdout.write(self.style.ERROR(f"خطأ: {error}"))
            raise CommandError(f"فشل فحص الجاهزية: {len(errors)} مشكلة حرجة.")

        self.stdout.write(self.style.SUCCESS(f"نجح فحص الجاهزية. التحذيرات: {len(warnings)}، الأخطاء: 0."))
