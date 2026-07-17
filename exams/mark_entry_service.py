from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied
from django.db import transaction

from academics.models import Enrollment
from teachers.models import TeacherAssignment

from .models import StudentMark


def resolve_mark_entry_scope(user, exam, assignment_id=None):
    """Return the optional teacher assignment and the allowed student list.

    Management users enter marks for the whole grade.  A teacher is restricted
    to the exact active assignment (year, grade, subject and section).  Both
    roles use the same screen and the same save service.
    """
    if user.is_superuser or user.is_staff:
        raise PermissionDenied(
            "الإدارة تراجع العلامات وتعتمدها، ولا تدخل أو تعدل قيم العلامات بدل المعلم."
        )

    teacher = getattr(user, "teacher_profile", None)
    if teacher is None or not teacher.is_active:
        raise PermissionDenied("لا تملك صلاحية إدخال علامات هذا الامتحان.")

    assignments = TeacherAssignment.objects.filter(
        teacher=teacher,
        academic_year=exam.academic_year,
        section__grade=exam.grade,
        subject=exam.subject,
        is_active=True,
    ).select_related("section", "section__grade", "subject", "academic_year")

    if assignment_id:
        assignments = assignments.filter(pk=assignment_id)

    assignment = assignments.first()
    if assignment is None:
        raise PermissionDenied("هذا الامتحان غير مرتبط بتكليف تدريسي فعال لك.")

    enrollments = Enrollment.objects.filter(
        section=assignment.section,
        grade=exam.grade,
        academic_year=exam.academic_year,
        status="active",
    ).select_related("student")
    return assignment, [item.student for item in enrollments]


def build_mark_rows(exam, students):
    existing = {
        mark.student_id: mark
        for mark in StudentMark.objects.filter(exam=exam, student__in=students)
    }
    return [
        {
            "student": student,
            "mark": existing.get(student.pk).mark if student.pk in existing else "",
            "notes": existing.get(student.pk).notes if student.pk in existing else "",
        }
        for student in students
    ]


def save_exam_marks(*, exam, students, payload, user):
    if not exam.can_edit_marks:
        return 0, ["الامتحان معتمد أو مقفل ولا يمكن تعديل علاماته."]

    allowed = {student.pk: student for student in students}
    parsed = []
    errors = []
    maximum = Decimal(exam.max_mark)

    for student_id, student in allowed.items():
        raw_mark = (payload.get(f"mark_{student_id}") or "").strip()
        notes = (payload.get(f"notes_{student_id}") or "").strip()
        if raw_mark == "":
            continue
        try:
            value = Decimal(raw_mark)
        except InvalidOperation:
            errors.append(f"علامة {student.full_name} غير صالحة.")
            continue
        if value < 0 or value > maximum:
            errors.append(f"علامة {student.full_name} يجب أن تكون بين 0 و{exam.max_mark}.")
            continue
        parsed.append((student, value, notes))

    if errors:
        return 0, errors

    saved = 0
    with transaction.atomic():
        for student, value, notes in parsed:
            mark = StudentMark.objects.filter(exam=exam, student=student).first()
            if mark is None:
                mark = StudentMark(
                    exam=exam,
                    student=student,
                    entered_by=user,
                )
            mark.mark = value
            mark.notes = notes
            mark.updated_by = user
            mark.save()
            saved += 1

        if saved and exam.status == "draft":
            exam.status = "open"
            exam.save(update_fields=["status"])

    return saved, []
