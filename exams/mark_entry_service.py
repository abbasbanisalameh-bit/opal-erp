from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, IntegrityError, transaction

from academics.models import Enrollment
from teachers.models import TeacherAssignment

from .models import StudentMark


_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def _normalize_decimal(value):
    """Normalize Arabic digits and decimal separators before Decimal parsing."""
    return (
        str(value or "")
        .translate(_ARABIC_DIGITS)
        .replace("٫", ".")
        .replace("٬", "")
        .replace(",", ".")
        .strip()
    )


def resolve_mark_entry_scope(user, exam, assignment_id=None):
    """Return the teacher assignment and the students the teacher may edit.

    The active teacher profile takes precedence over legacy ``is_staff`` flags.
    This keeps older teacher accounts working without granting them management
    access to any other screen.
    """
    teacher = getattr(user, "teacher_profile", None)
    if teacher is None or not teacher.is_active:
        if user.is_superuser or user.is_staff:
            raise PermissionDenied(
                "الإدارة تراجع العلامات وتعتمدها، ولا تدخل أو تعدل قيم العلامات بدل المعلم."
            )
        raise PermissionDenied("لا تملك صلاحية إدخال علامات هذا الامتحان.")

    assignments = TeacherAssignment.objects.filter(
        teacher=teacher,
        academic_year=exam.academic_year,
        section__grade=exam.grade,
        subject=exam.subject,
        is_active=True,
    ).select_related("section", "section__grade", "subject", "academic_year")

    if exam.section_id:
        assignments = assignments.filter(section_id=exam.section_id)
    if exam.teacher_assignment_id:
        assignments = assignments.filter(pk=exam.teacher_assignment_id)

    if assignment_id:
        try:
            assignment_id = int(assignment_id)
        except (TypeError, ValueError):
            raise PermissionDenied("معرف التكليف التدريسي غير صالح.")
        assignments = assignments.filter(pk=assignment_id)

    assignment = assignments.order_by("pk").first()
    if assignment is None:
        raise PermissionDenied("هذا الامتحان غير مرتبط بتكليف تدريسي فعال لك.")

    enrollments = Enrollment.objects.filter(
        section=assignment.section,
        grade=exam.grade,
        academic_year=exam.academic_year,
        status="active",
    ).select_related("student").order_by("student__full_name", "student_id")
    return assignment, [item.student for item in enrollments]


def build_mark_rows(exam, students):
    existing = {}
    # ``order_by`` makes the page resilient if an old database contains a
    # duplicate row that predates the current uniqueness constraint.
    for mark in StudentMark.objects.filter(exam=exam, student__in=students).order_by(
        "student_id", "-updated_at", "-pk"
    ):
        existing.setdefault(mark.student_id, mark)
    return [
        {
            "student": student,
            "mark": existing.get(student.pk).mark if student.pk in existing else "",
            "notes": existing.get(student.pk).notes if student.pk in existing else "",
        }
        for student in students
    ]


def save_exam_marks(*, exam, students, payload, user):
    """Validate and save an entire section atomically.

    Expected validation/data-integrity problems are returned to the screen as
    Arabic messages instead of escaping as a production HTTP 500 response.
    """
    if not exam.can_edit_marks:
        return 0, ["الامتحان معتمد أو مقفل ولا يمكن تعديل علاماته."]

    allowed = {student.pk: student for student in students}
    parsed = []
    errors = []
    maximum = Decimal(exam.max_mark)

    for student_id, student in allowed.items():
        raw_mark = _normalize_decimal(payload.get(f"mark_{student_id}"))
        notes = str(payload.get(f"notes_{student_id}") or "").strip()
        if raw_mark == "":
            continue
        try:
            value = Decimal(raw_mark)
        except (InvalidOperation, ValueError):
            errors.append(f"علامة {student.full_name} غير صالحة.")
            continue
        if not value.is_finite() or value < 0 or value > maximum:
            errors.append(f"علامة {student.full_name} يجب أن تكون بين 0 و{exam.max_mark}.")
            continue
        parsed.append((student, value, notes[:500]))

    if errors:
        return 0, errors

    saved = 0
    try:
        with transaction.atomic():
            for student, value, notes in parsed:
                records = list(
                    StudentMark.objects.select_for_update()
                    .filter(exam=exam, student=student)
                    .order_by("-updated_at", "-pk")
                )
                mark = records[0] if records else StudentMark(
                    exam=exam,
                    student=student,
                    entered_by=user,
                )
                # Repair only exact legacy duplicates for the same student/exam.
                if len(records) > 1:
                    StudentMark.objects.filter(pk__in=[row.pk for row in records[1:]]).delete()
                mark.mark = value
                mark.notes = notes
                if not mark.entered_by_id:
                    mark.entered_by = user
                mark.updated_by = user
                mark.save()
                saved += 1

            if saved and exam.status == "draft":
                exam.status = "open"
                exam.save(update_fields=["status"])
    except ValidationError as exc:
        messages = getattr(exc, "messages", None) or [str(exc)]
        return 0, [f"تعذر حفظ العلامات: {message}" for message in messages]
    except IntegrityError:
        return 0, ["تعذر حفظ العلامات بسبب تعارض في سجل طالب. أعد فتح الصفحة ثم حاول مرة أخرى."]
    except DatabaseError:
        return 0, ["تعذر الاتصال بقاعدة البيانات أثناء حفظ العلامات. لم يتم حفظ أي علامة."]

    return saved, []
