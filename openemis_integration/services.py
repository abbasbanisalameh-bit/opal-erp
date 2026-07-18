from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date

from academics.models import Enrollment, Grade, Section, Subject
from academics.canonical_services import resolve_grade, resolve_section
from attendance_v2.models import Attendance
from accounting.models import StudentInvoice, StudentPayment
from core.identifiers import normalize_identifier, normalize_phone
from core.models import AcademicYear, Branch, School
from core.choices import normalize_student_gender
from exams.models import Exam, StudentMark
from parent_portal.services import create_or_update_parent_family_for_student
from students.models import Student
from teachers.models import Teacher

from .models import OpenEMISSettings, OpenEMISSyncLog


def active_school():
    return School.objects.filter(is_active=True).first() or School.objects.create(name="OPAL School")


def get_openemis_settings(school=None):
    school = school or active_school()
    settings, _ = OpenEMISSettings.objects.get_or_create(school=school)
    return settings


def _user_or_none(user):
    return user if getattr(user, "is_authenticated", False) else None


def _current_enrollment(student):
    return (
        student.enrollments.filter(status="active")
        .select_related("academic_year", "grade", "section", "section__branch")
        .order_by("-academic_year__start_date")
        .first()
    )


def build_student_payload(student):
    """Build one canonical OPAL payload suitable for an official adapter."""
    enrollment = _current_enrollment(student)
    family_link = student.family_links.filter(is_active=True).select_related("family").first()
    family = family_link.family if family_link else None

    marks = [
        {
            "academic_year": row.exam.academic_year.name,
            "semester": row.exam.semester.code if row.exam.semester else "",
            "grade": row.exam.grade.name,
            "subject": row.exam.subject.name,
            "exam_type": row.exam.exam_type,
            "max_mark": str(row.exam.max_mark),
            "mark": str(row.mark),
            "exam_date": row.exam.exam_date.isoformat() if row.exam.exam_date else None,
            "notes": row.notes,
        }
        for row in student.marks.select_related(
            "exam", "exam__academic_year", "exam__semester", "exam__grade", "exam__subject"
        ).all()
    ]
    attendance = [
        {
            "date": row.date.isoformat(),
            "status": row.status,
            "arrival_time": row.arrival_time.isoformat() if row.arrival_time else None,
            "departure_time": row.departure_time.isoformat() if row.departure_time else None,
            "excuse_reason": row.excuse_reason,
            "notes": row.notes,
        }
        for row in student.attendance_records.all().order_by("date")
    ]
    invoices = [
        {
            "invoice_id": row.pk,
            "academic_year": row.academic_year.name if row.academic_year else "",
            "fee_category": row.fee_category.name,
            "amount": str(row.amount),
            "paid": row.paid,
            "remaining": str(row.remaining),
            "due_date": row.due_date.isoformat() if row.due_date else None,
        }
        for row in student.invoices.select_related("academic_year", "fee_category").all()
    ]
    payments = [
        {
            "payment_id": row.pk,
            "invoice_id": row.invoice_id,
            "amount": str(row.amount),
            "date": row.payment_date.isoformat() if row.payment_date else None,
            "notes": row.notes,
        }
        for row in StudentPayment.objects.filter(invoice__student=student).select_related("invoice").order_by("payment_date", "pk")
    ]

    return {
        "student": {
            "student_number": student.student_number,
            "ministry_student_id": student.ministry_student_id,
            "national_id": student.national_id,
            "full_name": student.full_name,
            "father_name": student.father_name,
            "mother_name": student.mother_name,
            "gender": student.gender,
            "blood_type": student.blood_type,
            "address": student.address,
            "medical_notes": student.medical_notes,
            "status": student.status,
            "enrollment_date": student.enrollment_date.isoformat() if student.enrollment_date else None,
            "source": student.source,
            "extra_fields": student.openemis_data,
        },
        "guardian": {
            "name": family.guardian_name if family else student.guardian_name,
            "identity_type": family.identity_type if family else "national",
            "identity_number": family.identity_number if family else "",
            "phone": family.phone if family else student.phone,
            "family_code": family.family_code if family else "",
        },
        "enrollment": {
            "academic_year": enrollment.academic_year.name if enrollment else "",
            "grade": enrollment.grade.name if enrollment else student.grade,
            "section": enrollment.section.name if enrollment and enrollment.section else student.section,
            "branch": enrollment.section.branch.name if enrollment and enrollment.section else "",
            "status": enrollment.status if enrollment else student.status,
        },
        "attendance": attendance,
        "marks": marks,
        "finance": {
            "total_fees": str(student.fees_total),
            "total_paid": str(student.fees_paid),
            "remaining": str(student.fees_remaining),
            "invoices": invoices,
            "payments": payments,
        },
    }


def build_teacher_payload(teacher):
    return {
        "employee_number": teacher.employee_number,
        "ministry_teacher_id": teacher.ministry_teacher_id,
        "national_id": teacher.national_id,
        "full_name": teacher.full_name,
        "gender": teacher.gender,
        "birth_date": teacher.birth_date.isoformat() if teacher.birth_date else None,
        "phone": teacher.phone,
        "email": teacher.email,
        "address": teacher.address,
        "specialization": teacher.specialization,
        "qualification": teacher.qualification,
        "hire_date": teacher.hire_date.isoformat() if teacher.hire_date else None,
        "branch": teacher.branch.name if teacher.branch else "",
        "is_active": teacher.is_active,
        "extra_fields": teacher.openemis_data,
    }


def test_openemis_connection(user=None):
    school = active_school()
    settings = get_openemis_settings(school)
    log = OpenEMISSyncLog.objects.create(
        school=school,
        operation="test_connection",
        status="pending",
        created_by=_user_or_none(user),
    )
    if not settings.is_enabled:
        log.status = "skipped"
        log.message = "التكامل غير مفعل من الإعدادات."
    elif not settings.base_url:
        log.status = "failed"
        log.message = "رابط OpenEMIS غير مضبوط."
    else:
        log.status = "success"
        log.message = "إعدادات الربط محفوظة. الاختبار الشبكي الفعلي يحتاج مواصفات API الرسمية وآلية المصادقة من الوزارة."
        settings.last_tested_at = timezone.now()
        settings.save(update_fields=["last_tested_at"])
    log.completed_at = timezone.now()
    log.save(update_fields=["status", "message", "completed_at"])
    return log


def queue_student_push(student, user=None, reason="registration"):
    school = active_school()
    settings = get_openemis_settings(school)
    payload = build_student_payload(student)
    status = "pending" if settings.is_enabled and settings.auto_push_registration else "skipped"
    message = "جاهز للإرسال عبر محول API الرسمي." if status == "pending" else "لم يتم الإرسال لأن التكامل أو الإرسال التلقائي غير مفعل."
    return OpenEMISSyncLog.objects.create(
        school=school,
        student=student,
        operation="push_student",
        status=status,
        message=message,
        request_payload={"reason": reason, "payload": payload},
        created_by=_user_or_none(user),
    )


def mark_student_synced(student, ministry_student_id="", user=None, response=None):
    if ministry_student_id:
        student.ministry_student_id = ministry_student_id
    student.ministry_sync_status = "synced"
    student.last_ministry_sync_at = timezone.now()
    student.save(update_fields=["ministry_student_id", "ministry_sync_status", "last_ministry_sync_at"])
    return OpenEMISSyncLog.objects.create(
        school=active_school(),
        student=student,
        operation="pull_student",
        status="success",
        message="تم تحديث حالة مزامنة الطالب داخل OPAL.",
        response_payload=response or {},
        created_by=_user_or_none(user),
        completed_at=timezone.now(),
    )


def _student_lookup(data):
    ministry_id = normalize_identifier(data.get("ministry_student_id") or data.get("id") or "")
    national_id = normalize_identifier(data.get("national_id") or "")
    student_number = str(data.get("student_number") or "").strip()
    matches = []
    if ministry_id:
        matches.append(Student.objects.filter(ministry_student_id=ministry_id).first())
    if national_id:
        matches.append(Student.objects.filter(national_id=national_id).first())
    if student_number:
        matches.append(Student.objects.filter(student_number=student_number).first())
    resolved = {item.pk: item for item in matches if item is not None}
    if len(resolved) > 1:
        raise ValidationError(
            "بيانات OpenEMIS متعارضة: المعرف الوزاري أو الرقم الوطني أو رقم الطالب "
            "تشير إلى أكثر من طالب داخل OPAL."
        )
    return next(iter(resolved.values()), None)


def _resolve_enrollment(student, payload, school):
    data = payload.get("enrollment") or {}
    if not data:
        return None
    year_name = str(data.get("academic_year") or "").strip()
    year = AcademicYear.objects.filter(school=school, name=year_name, is_closed=False).first() if year_name else None
    year = year or AcademicYear.objects.filter(school=school, is_current=True, is_closed=False).first()
    if not year:
        return None

    grade_name = str(data.get("grade") or "").strip()
    if not grade_name:
        return None
    grade, _ = resolve_grade(school=school, name=grade_name)

    section = None
    section_name = str(data.get("section") or "").strip()
    if section_name:
        branch_name = str(data.get("branch") or "الرئيسي").strip()
        branch, _ = Branch.objects.get_or_create(
            school=school, name=branch_name, defaults={"is_main": branch_name == "الرئيسي"}
        )
        section, _ = resolve_section(
            academic_year=year, branch=branch, grade=grade, name=section_name
        )

    enrollment, _ = Enrollment.objects.update_or_create(
        student=student,
        academic_year=year,
        defaults={
            "grade": grade,
            "section": section,
            "status": data.get("status") or "active",
            "joined_at": parse_date(str(data.get("joined_at") or "")) or student.enrollment_date,
        },
    )
    return enrollment


def _sync_attendance(student, payload):
    count = 0
    for item in payload.get("attendance") or []:
        date = parse_date(str(item.get("date") or ""))
        if not date:
            continue
        status = item.get("status") or "present"
        if status not in dict(Attendance.STATUS):
            status = "present"
        enrollment = _current_enrollment(student)
        Attendance.objects.update_or_create(
            student=student,
            date=date,
            defaults={
                "academic_year": enrollment.academic_year if enrollment else None,
                "grade": enrollment.grade if enrollment else None,
                "section": enrollment.section if enrollment else None,
                "status": status,
                "excuse_reason": item.get("excuse_reason") or "",
                "notes": item.get("notes") or "",
            },
        )
        count += 1
    return count


def _sync_marks(student, payload, school, enrollment=None):
    count = 0
    for item in payload.get("marks") or []:
        year_name = str(item.get("academic_year") or "").strip()
        year = AcademicYear.objects.filter(school=school, name=year_name).first() if year_name else None
        year = year or (enrollment.academic_year if enrollment else None)
        if not year:
            continue
        semester_code = item.get("semester") or "first"
        semester = year.semesters.filter(code=semester_code).first()
        if not semester:
            continue
        grade_name = str(item.get("grade") or "").strip()
        grade = Grade.objects.filter(school=school, name=grade_name).first() if grade_name else None
        grade = grade or (enrollment.grade if enrollment else None)
        if not grade:
            continue
        subject_name = str(item.get("subject") or "").strip()
        if not subject_name:
            continue
        subject, _ = Subject.objects.get_or_create(grade=grade, name=subject_name)
        exam_type = item.get("exam_type") or "first"
        if exam_type not in dict(Exam.EXAM_TYPES):
            continue
        exam, _ = Exam.objects.get_or_create(
            academic_year=year,
            semester=semester,
            grade=grade,
            subject=subject,
            exam_type=exam_type,
            defaults={"exam_date": parse_date(str(item.get("exam_date") or ""))},
        )
        try:
            raw_mark = Decimal(str(item.get("mark") or 0))
            source_max = Decimal(str(item.get("max_mark") or exam.max_mark))
        except (ArithmeticError, ValueError):
            continue
        if source_max <= 0:
            continue
        official_max = Decimal(exam.max_mark)
        converted_mark = raw_mark * official_max / source_max
        converted_mark = min(max(converted_mark, Decimal("0")), official_max).quantize(Decimal("0.01"))
        StudentMark.objects.update_or_create(
            exam=exam,
            student=student,
            defaults={"mark": converted_mark, "notes": item.get("notes") or ""},
        )
        count += 1
    return count


@transaction.atomic
def upsert_student_from_openemis(payload, user=None):
    """Import one normalized OpenEMIS record into the official OPAL models only."""
    school = active_school()
    data = payload.get("student") or payload
    student = _student_lookup(data)
    created = student is None
    if created:
        from admissions.services import generate_student_number
        student = Student(student_number=data.get("student_number") or generate_student_number(), grade="")

    mapping = {
        "ministry_student_id": data.get("ministry_student_id") or data.get("id") or "",
        "national_id": data.get("national_id") or "",
        "full_name": data.get("full_name") or data.get("name") or student.full_name or "طالب OpenEMIS",
        "father_name": data.get("father_name") or "",
        "mother_name": data.get("mother_name") or "",
        "gender": normalize_student_gender(data.get("gender")),
        "blood_type": data.get("blood_type") or "",
        "address": data.get("address") or "",
        "medical_notes": data.get("medical_notes") or "",
        "status": data.get("status") or "active",
        "enrollment_date": parse_date(str(data.get("enrollment_date") or "")) or student.enrollment_date,
    }
    for field, value in mapping.items():
        if value not in (None, "") or field in {"father_name", "mother_name", "gender", "blood_type", "address", "medical_notes"}:
            setattr(student, field, value)
    student.source = "openemis"
    student.openemis_data = payload
    student.ministry_sync_status = "synced"
    student.last_ministry_sync_at = timezone.now()
    student.is_active = student.status != "archived"
    student.save()

    guardian = payload.get("guardian") or {}
    if guardian:
        create_or_update_parent_family_for_student(
            student,
            guardian_name=guardian.get("name") or guardian.get("full_name") or "ولي أمر",
            phone=guardian.get("phone") or "",
            school=school,
            identity_type=guardian.get("identity_type") or "national",
            identity_number=guardian.get("identity_number") or guardian.get("national_id") or "",
            relation=guardian.get("relation") or "ولي أمر",
            source="openemis",
            openemis_data=guardian,
            email=guardian.get("email") or "",
            secondary_phone=guardian.get("secondary_phone") or "",
            job_title=guardian.get("job_title") or guardian.get("job") or "",
            address=guardian.get("address") or data.get("address") or "",
        )

    enrollment = _resolve_enrollment(student, payload, school)
    attendance_count = _sync_attendance(student, payload)
    marks_count = _sync_marks(student, payload, school, enrollment)

    log = OpenEMISSyncLog.objects.create(
        school=school,
        student=student,
        operation="pull_student",
        status="success",
        message=f"تم {'إنشاء' if created else 'تحديث'} الطالب وربطه بولي الأمر والتسجيل؛ الحضور: {attendance_count}، العلامات: {marks_count}.",
        response_payload=payload,
        created_by=_user_or_none(user),
        completed_at=timezone.now(),
    )
    settings = get_openemis_settings(school)
    settings.last_sync_at = timezone.now()
    settings.save(update_fields=["last_sync_at"])
    return student, created, log


@transaction.atomic
def upsert_teacher_from_openemis(data, user=None):
    school = active_school()
    ministry_id = str(data.get("ministry_teacher_id") or data.get("id") or "").strip()
    national_id = normalize_identifier(data.get("national_id") or "")
    employee_number = str(data.get("employee_number") or "").strip()
    candidates = []
    if ministry_id:
        candidates.append(Teacher.objects.filter(ministry_teacher_id=normalize_identifier(ministry_id)).first())
    if national_id:
        candidates.append(Teacher.objects.filter(national_id=national_id).first())
    if employee_number:
        candidates.append(Teacher.objects.filter(employee_number=employee_number).first())
    resolved = {item.pk: item for item in candidates if item is not None}
    if len(resolved) > 1:
        raise ValidationError(
            "بيانات OpenEMIS متعارضة: معرف المعلم الوزاري أو رقمه الوطني أو الوظيفي "
            "تشير إلى أكثر من معلم داخل OPAL."
        )
    teacher = next(iter(resolved.values()), None)
    created = teacher is None
    if created:
        employee_number = employee_number or f"OPENEMIS-{ministry_id or timezone.now().strftime('%Y%m%d%H%M%S')}"
        teacher = Teacher(employee_number=employee_number, school=school)

    branch_name = str(data.get("branch") or "").strip()
    if branch_name:
        teacher.branch, _ = Branch.objects.get_or_create(school=school, name=branch_name)
    for field in ["national_id", "full_name", "gender", "phone", "email", "address", "specialization", "qualification"]:
        if field in data:
            setattr(teacher, field, data.get(field) or "")
    teacher.birth_date = parse_date(str(data.get("birth_date") or "")) or teacher.birth_date
    teacher.hire_date = parse_date(str(data.get("hire_date") or "")) or teacher.hire_date
    teacher.ministry_teacher_id = ministry_id
    teacher.source = "openemis"
    teacher.openemis_data = data
    teacher.is_active = bool(data.get("is_active", True))
    teacher.save()
    return teacher, created


@transaction.atomic
def import_openemis_payload(payload, user=None):
    students_payload = payload.get("students") if isinstance(payload, dict) else None
    teachers_payload = payload.get("teachers") if isinstance(payload, dict) else None
    if students_payload is None:
        students_payload = [payload]
    results = {"students_created": 0, "students_updated": 0, "teachers_created": 0, "teachers_updated": 0}
    for item in students_payload or []:
        _, created, _ = upsert_student_from_openemis(item, user=user)
        results["students_created" if created else "students_updated"] += 1
    for item in teachers_payload or []:
        _, created = upsert_teacher_from_openemis(item, user=user)
        results["teachers_created" if created else "teachers_updated"] += 1
    return results
