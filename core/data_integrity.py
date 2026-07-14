from collections import defaultdict

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from .models import DataIntegrityIssue, DataIntegrityRun


class IntegrityAuditor:
    def __init__(self, *, fix_safe=False, user=None):
        self.fix_safe = fix_safe
        self.run = DataIntegrityRun.objects.create(mode="fix_safe" if fix_safe else "scan", created_by=user)

    def issue(self, code, description, *, severity="warning", model_name="", object_id="", fix=None, resolution=""):
        item = DataIntegrityIssue.objects.create(
            run=self.run, code=code, severity=severity, model_name=model_name,
            object_id=str(object_id or ""), description=description, is_fixable=bool(fix),
        )
        if self.fix_safe and fix:
            try:
                fix()
            except Exception as exc:
                item.resolution = f"فشل الإصلاح الآمن: {exc}"
                item.save(update_fields=["resolution"])
            else:
                item.is_fixed = True
                item.resolution = resolution or "تم الإصلاح تلقائيًا وفق المصدر الرسمي."
                item.save(update_fields=["is_fixed", "resolution"])
        return item

    def finish(self):
        issues = self.run.issues.all()
        self.run.total_issues = issues.count()
        self.run.critical_count = issues.filter(severity="critical", is_fixed=False).count()
        self.run.warning_count = issues.filter(severity="warning", is_fixed=False).count()
        self.run.fixed_count = issues.filter(is_fixed=True).count()
        self.run.completed_at = timezone.now()
        self.run.save(update_fields=["total_issues", "critical_count", "warning_count", "fixed_count", "completed_at"])
        return self.run


@transaction.atomic
def run_integrity_audit(*, fix_safe=False, user=None):
    from academics.models import Enrollment, Section
    from accounting.models import StudentInvoice
    from attendance_v2.models import Attendance
    from documents.models import IssuedDocument
    from exams.models import Exam, StudentMark
    from parent_portal.models import Family, FamilyStudent
    from parent_portal.services import create_or_update_parent_family_for_student, normalize_phone
    from students.models import Student
    from teachers.models import Teacher, TeacherAssignment
    from timetable.models import TimetableEntry

    audit = IntegrityAuditor(fix_safe=fix_safe, user=user)

    # Duplicate official identities are never merged automatically.
    for field, code, label in (
        ("national_id", "STUDENT_DUPLICATE_NATIONAL_ID", "الرقم الوطني"),
        ("ministry_student_id", "STUDENT_DUPLICATE_MINISTRY_ID", "الرقم الوزاري"),
    ):
        rows = Student.objects.exclude(**{field: ""}).values(field).annotate(total=Count("id")).filter(total__gt=1)
        for row in rows:
            ids = list(Student.objects.filter(**{field: row[field]}).values_list("id", flat=True))
            audit.issue(code, f"{label} {row[field]} مستخدم في {row['total']} سجلات طلاب.", severity="critical", model_name="students.Student", object_id=",".join(map(str, ids)))

    active_enrollments = Enrollment.objects.filter(status="active").select_related("student", "grade", "section", "academic_year")
    active_by_student = defaultdict(list)
    enrollment_by_student_year = {}
    for enrollment in active_enrollments:
        active_by_student[enrollment.student_id].append(enrollment)
        enrollment_by_student_year[(enrollment.student_id, enrollment.academic_year_id)] = enrollment
        if enrollment.section_id and enrollment.section.grade_id != enrollment.grade_id:
            audit.issue("ENROLLMENT_SECTION_GRADE_MISMATCH", f"قيد الطالب {enrollment.student} في شعبة لا تتبع صفه.", severity="critical", model_name="academics.Enrollment", object_id=enrollment.pk)
        if enrollment.section_id and enrollment.section.academic_year_id and enrollment.section.academic_year_id != enrollment.academic_year_id:
            audit.issue("ENROLLMENT_SECTION_YEAR_MISMATCH", f"قيد الطالب {enrollment.student} في شعبة لا تتبع عامه.", severity="critical", model_name="academics.Enrollment", object_id=enrollment.pk)

    for student_id, rows in active_by_student.items():
        if len(rows) > 1:
            audit.issue("STUDENT_MULTIPLE_ACTIVE_ENROLLMENTS", f"للطالب #{student_id} أكثر من قيد نشط ({len(rows)}).", severity="critical", model_name="students.Student", object_id=student_id)

    for student in Student.objects.all().iterator():
        rows = active_by_student.get(student.pk, [])
        if len(rows) == 1:
            enrollment = rows[0]
            expected_grade = enrollment.grade.name if enrollment.grade_id else ""
            expected_section = enrollment.section.name if enrollment.section_id else ""
            if student.grade != expected_grade or student.section != expected_section:
                def fix_snapshot(student=student, grade=expected_grade, section=expected_section):
                    Student.objects.filter(pk=student.pk).update(grade=grade, section=section)
                audit.issue("STUDENT_ACADEMIC_SNAPSHOT_MISMATCH", f"صف/شعبة الطالب {student.full_name} لا يطابق القيد النشط.", model_name="students.Student", object_id=student.pk, fix=fix_snapshot, resolution="تمت مزامنة نسخة الصف والشعبة من القيد النشط.")
            if student.status != "active" or not student.is_active:
                def fix_status(student=student):
                    Student.objects.filter(pk=student.pk).update(status="active", is_active=True)
                audit.issue("STUDENT_ACTIVE_STATUS_MISMATCH", f"للطالب {student.full_name} قيد نشط لكن حالة ملفه غير نشطة.", severity="critical", model_name="students.Student", object_id=student.pk, fix=fix_status)
        elif not rows and student.status == "active" and student.is_active:
            audit.issue("STUDENT_WITHOUT_ACTIVE_ENROLLMENT", f"الطالب النشط {student.full_name} لا يملك قيدًا أكاديميًا نشطًا.", severity="warning", model_name="students.Student", object_id=student.pk)

        links = list(FamilyStudent.objects.filter(student=student, is_active=True).select_related("family"))
        if not links:
            fix = None
            if student.guardian_name and normalize_phone(student.phone):
                fix = lambda student=student: create_or_update_parent_family_for_student(
                    student, guardian_name=student.guardian_name, phone=student.phone, school=None
                )
            audit.issue("STUDENT_WITHOUT_ACTIVE_FAMILY", f"الطالب {student.full_name} غير مرتبط بأسرة نشطة.", model_name="students.Student", object_id=student.pk, fix=fix, resolution="تم إنشاء/استعادة رابط الأسرة من بيانات ولي الأمر الموجودة.")
        elif len(links) > 1:
            audit.issue("STUDENT_MULTIPLE_ACTIVE_FAMILIES", f"الطالب {student.full_name} مرتبط بأكثر من أسرة نشطة.", severity="critical", model_name="students.Student", object_id=student.pk)

    def duplicate_family_values(field, code, label, normalize=False):
        groups = defaultdict(list)
        for family in Family.objects.exclude(**{field: ""}).only("id", field):
            value = getattr(family, field) or ""
            key = normalize_phone(value) if normalize else value.strip().lower()
            if key:
                groups[key].append(family.pk)
        for value, ids in groups.items():
            if len(ids) > 1:
                audit.issue(code, f"{label} {value} مرتبط بأكثر من أسرة.", severity="critical", model_name="parent_portal.Family", object_id=",".join(map(str, ids)))
    duplicate_family_values("phone", "FAMILY_DUPLICATE_PHONE", "الهاتف", normalize=True)
    duplicate_family_values("guardian_national_id", "FAMILY_DUPLICATE_NATIONAL_ID", "الرقم الوطني")
    for family in Family.objects.all():
        if not family.children.filter(is_active=True).exists():
            audit.issue("FAMILY_WITHOUT_CHILDREN", f"الأسرة #{family.pk} لا تملك أبناء مرتبطين بنشاط.", model_name="parent_portal.Family", object_id=family.pk)
        if not family.user_id:
            audit.issue("FAMILY_WITHOUT_ACCOUNT", f"الأسرة #{family.pk} لا تملك حساب دخول.", model_name="parent_portal.Family", object_id=family.pk)

    duplicate_teachers = Teacher.objects.exclude(national_id="").values("national_id").annotate(total=Count("id")).filter(total__gt=1)
    for row in duplicate_teachers:
        ids = list(Teacher.objects.filter(national_id=row["national_id"]).values_list("id", flat=True))
        audit.issue("TEACHER_DUPLICATE_NATIONAL_ID", f"الرقم الوطني {row['national_id']} مرتبط بأكثر من معلم.", severity="critical", model_name="teachers.Teacher", object_id=",".join(map(str, ids)))
    for teacher in Teacher.objects.select_related("user", "school"):
        if not teacher.user_id:
            audit.issue("TEACHER_WITHOUT_ACCOUNT", f"المعلم {teacher.full_name} لا يملك حساب دخول.", model_name="teachers.Teacher", object_id=teacher.pk)
        elif teacher.user.is_active != teacher.is_active:
            def fix_teacher_user(teacher=teacher):
                type(teacher.user).objects.filter(pk=teacher.user_id).update(is_active=teacher.is_active)
            audit.issue("TEACHER_ACCOUNT_STATUS_MISMATCH", f"حالة حساب المعلم {teacher.full_name} لا تطابق حالة ملفه.", model_name="teachers.Teacher", object_id=teacher.pk, fix=fix_teacher_user)

    for assignment in TeacherAssignment.objects.select_related("teacher__school", "academic_year", "section__branch__school", "section__grade", "subject"):
        problems = []
        if assignment.academic_year.school_id != assignment.teacher.school_id: problems.append("العام من مدرسة أخرى")
        if assignment.section.branch.school_id != assignment.teacher.school_id: problems.append("الشعبة من مدرسة أخرى")
        if assignment.section.academic_year_id != assignment.academic_year_id: problems.append("الشعبة من عام آخر")
        if assignment.subject.grade_id and assignment.subject.grade_id != assignment.section.grade_id: problems.append("المادة من صف آخر")
        if problems:
            audit.issue("TEACHER_ASSIGNMENT_MISMATCH", f"تكليف #{assignment.pk}: {'، '.join(problems)}.", severity="critical", model_name="teachers.TeacherAssignment", object_id=assignment.pk)

    for section in Section.objects.all():
        if section.capacity and section.active_enrollment_count > section.capacity:
            audit.issue("SECTION_OVER_CAPACITY", f"الشعبة {section} تتجاوز السعة ({section.active_enrollment_count}/{section.capacity}).", model_name="academics.Section", object_id=section.pk)

    slots = defaultdict(list)
    for entry in TimetableEntry.objects.filter(is_active=True).values("pk", "academic_year_id", "day", "time_slot_id", "section_id", "teacher_id", "room"):
        slots[(entry["academic_year_id"], entry["day"], entry["time_slot_id"])].append(entry)
    for entries in slots.values():
        for field, label in (("section_id", "الشعبة"), ("teacher_id", "المعلم"), ("room", "الغرفة")):
            groups = defaultdict(list)
            for entry in entries:
                if entry[field] not in (None, ""): groups[entry[field]].append(entry["pk"])
            for ids in groups.values():
                if len(ids) > 1:
                    audit.issue("TIMETABLE_CONFLICT", f"تعارض {label} بين الحصص {ids}.", severity="critical", model_name="timetable.TimetableEntry", object_id=",".join(map(str, ids)))

    for invoice in StudentInvoice.objects.prefetch_related("payments"):
        if invoice.status == "cancelled" and invoice.payments.filter(status="posted").exists():
            audit.issue("CANCELLED_INVOICE_WITH_PAYMENTS", f"الفاتورة {invoice.invoice_number} ملغاة ولها دفعات مرحلة.", severity="critical", model_name="accounting.StudentInvoice", object_id=invoice.pk)
            continue
        if invoice.total_paid > invoice.net_amount:
            audit.issue("INVOICE_OVERPAID", f"الفاتورة {invoice.invoice_number} مدفوعة بأكثر من صافي قيمتها.", severity="critical", model_name="accounting.StudentInvoice", object_id=invoice.pk)
            continue
        expected = "paid" if invoice.remaining <= 0 else ("partial" if invoice.total_paid > 0 else "open")
        expected_paid = expected == "paid"
        if invoice.status != expected or invoice.paid != expected_paid:
            audit.issue("INVOICE_STATUS_MISMATCH", f"حالة الفاتورة {invoice.invoice_number} لا تطابق دفعاتها.", model_name="accounting.StudentInvoice", object_id=invoice.pk, fix=lambda invoice=invoice: invoice.sync_status(), resolution=f"تمت مزامنة الحالة إلى {expected}.")

    for exam in Exam.objects.select_related("semester", "academic_year"):
        if exam.status in {"approved", "published", "closed"} and not exam.is_locked:
            audit.issue("EXAM_PUBLISHED_NOT_LOCKED", f"الامتحان {exam} معتمد/منشور لكنه غير مقفل.", severity="critical", model_name="exams.Exam", object_id=exam.pk, fix=lambda exam=exam: Exam.objects.filter(pk=exam.pk).update(is_locked=True), resolution="تم قفل الامتحان المنشور.")
        if exam.semester_id and exam.semester.academic_year_id != exam.academic_year_id:
            audit.issue("EXAM_SEMESTER_YEAR_MISMATCH", f"الامتحان {exam} مرتبط بفصل من عام آخر.", severity="critical", model_name="exams.Exam", object_id=exam.pk)
    for mark in StudentMark.objects.select_related("exam", "student"):
        if mark.mark < 0 or mark.mark > mark.exam.max_mark:
            audit.issue("INVALID_STUDENT_MARK", f"علامة الطالب {mark.student} في {mark.exam} خارج المجال الصحيح.", severity="critical", model_name="exams.StudentMark", object_id=mark.pk)

    for record in Attendance.objects.exclude(academic_year=None).select_related("student", "section"):
        enrollment = enrollment_by_student_year.get((record.student_id, record.academic_year_id))
        if enrollment is None:
            audit.issue("ATTENDANCE_WITHOUT_ENROLLMENT", f"سجل حضور #{record.pk} بلا قيد نشط مطابق للطالب والعام.", model_name="attendance_v2.Attendance", object_id=record.pk)
        elif record.section_id and enrollment.section_id != record.section_id:
            audit.issue("ATTENDANCE_SECTION_MISMATCH", f"شعبة الحضور #{record.pk} لا تطابق قيد الطالب.", model_name="attendance_v2.Attendance", object_id=record.pk)

    for document in IssuedDocument.objects.filter(status="cancelled"):
        if not document.cancelled_at or not document.cancellation_reason.strip():
            audit.issue("CANCELLED_DOCUMENT_INCOMPLETE", f"الوثيقة {document.document_number} ملغاة دون بيانات إلغاء مكتملة.", severity="critical", model_name="documents.IssuedDocument", object_id=document.pk)

    return audit.finish()
