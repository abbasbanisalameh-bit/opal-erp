from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import AcademicYear


EXPECTED_SEMESTER_CODES = {"first", "second"}


def academic_year_closure_report(year):
    """Return closure blockers, warnings and counts without changing data."""
    from academics.models import Enrollment
    from accounting.models import StudentInvoice
    from attendance_v2.models import Attendance
    from exams.models import Exam
    from teachers.models import TeacherAssignment
    from timetable.models import TimetableEntry

    blockers = []
    warnings = []
    semester_codes = set(year.semesters.values_list("code", flat=True))
    if semester_codes != EXPECTED_SEMESTER_CODES or year.semesters.count() != 2:
        blockers.append("يجب أن يحتوي العام على الفصلين الرسميين فقط قبل الإغلاق.")

    enrollments = Enrollment.objects.filter(academic_year=year)
    active_enrollments = enrollments.filter(status="active").count()
    if active_enrollments:
        blockers.append(
            f"يوجد {active_enrollments} قيدًا نشطًا؛ يجب ترفيع الطلاب أو تخريجهم أو إنهاء قيودهم أولًا."
        )

    exams = Exam.objects.filter(academic_year=year)
    exam_count = exams.count()
    unfinished_exams = exams.exclude(status="closed", is_locked=True).count()
    if unfinished_exams:
        blockers.append(f"يوجد {unfinished_exams} امتحانًا غير مغلق أو غير مقفل.")
    if not exam_count and enrollments.exists():
        warnings.append("لا توجد امتحانات مسجلة لهذا العام رغم وجود قيود طلاب.")

    outstanding_invoices = StudentInvoice.objects.filter(academic_year=year).exclude(
        status__in=["paid", "cancelled"]
    ).count()
    if outstanding_invoices:
        warnings.append(
            f"يوجد {outstanding_invoices} قيد رسوم غير مسدد بالكامل؛ سيبقى التحصيل متاحًا بعد إغلاق العام."
        )

    metrics = {
        "enrollments": enrollments.count(),
        "active_enrollments": active_enrollments,
        "exams": exam_count,
        "unfinished_exams": unfinished_exams,
        "attendance_to_lock": Attendance.objects.filter(academic_year=year, is_locked=False).count(),
        "assignments_to_deactivate": TeacherAssignment.objects.filter(academic_year=year, is_active=True).count(),
        "timetable_to_deactivate": TimetableEntry.objects.filter(academic_year=year, is_active=True).count(),
        "outstanding_invoices": outstanding_invoices,
    }
    return {"blockers": blockers, "warnings": warnings, "metrics": metrics}


@transaction.atomic
def close_academic_year(*, year, user, notes=""):
    """Close a validated year while preserving its historical records."""
    from academics.models import Section
    from admissions.models import GradeFee
    from attendance_v2.models import Attendance
    from curriculum.models import Curriculum
    from teachers.models import Homework, TeacherAssignment
    from timetable.models import TimetableEntry

    locked_year = AcademicYear.objects.select_for_update().get(pk=year.pk)
    if locked_year.is_closed:
        raise ValidationError("العام الدراسي مغلق بالفعل.")

    report = academic_year_closure_report(locked_year)
    if report["blockers"]:
        raise ValidationError(report["blockers"])

    locked_year.is_current = False
    locked_year.is_closed = True
    locked_year.closed_at = timezone.now()
    locked_year.closed_by = user if getattr(user, "is_authenticated", False) else None
    locked_year.closure_notes = (notes or "").strip()
    locked_year.save(
        update_fields=["is_current", "is_closed", "closed_at", "closed_by", "closure_notes"]
    )

    locked_year.semesters.update(is_current=False)
    attendance_locked = Attendance.objects.filter(academic_year=locked_year, is_locked=False).update(
        is_locked=True,
        updated_by=user if getattr(user, "is_authenticated", False) else None,
    )
    assignment_ids = list(
        TeacherAssignment.objects.filter(academic_year=locked_year, is_active=True).values_list("pk", flat=True)
    )
    homework_deactivated = Homework.objects.filter(
        assignment_id__in=assignment_ids,
        is_active=True,
    ).update(is_active=False)
    assignments_deactivated = TeacherAssignment.objects.filter(pk__in=assignment_ids).update(is_active=False)
    timetable_deactivated = TimetableEntry.objects.filter(
        academic_year=locked_year,
        is_active=True,
    ).update(is_active=False)
    sections_deactivated = Section.objects.filter(
        academic_year=locked_year,
        is_active=True,
    ).update(is_active=False)
    curricula_deactivated = Curriculum.objects.filter(
        academic_year=locked_year,
        is_active=True,
    ).update(is_active=False)
    fees_deactivated = GradeFee.objects.filter(
        academic_year=locked_year,
        is_active=True,
    ).update(is_active=False)

    return locked_year, {
        "attendance_locked": attendance_locked,
        "assignments_deactivated": assignments_deactivated,
        "homework_deactivated": homework_deactivated,
        "timetable_deactivated": timetable_deactivated,
        "sections_deactivated": sections_deactivated,
        "curricula_deactivated": curricula_deactivated,
        "fees_deactivated": fees_deactivated,
    }


@transaction.atomic
def activate_academic_year(*, year):
    """Make an open year current and select its date-appropriate semester."""
    locked_year = AcademicYear.objects.select_for_update().get(pk=year.pk)
    if locked_year.is_closed:
        raise ValidationError("لا يمكن تفعيل عام مغلق. أنشئ أو اختر عامًا مفتوحًا.")

    locked_year.is_current = True
    locked_year.save(update_fields=["is_current"])
    locked_year.ensure_semesters()

    today = timezone.localdate()
    semesters = list(locked_year.semesters.order_by("start_date", "code"))
    selected = next((item for item in semesters if item.start_date <= today <= item.end_date), None)
    if selected is None and semesters:
        selected = semesters[0] if today < semesters[-1].start_date else semesters[-1]
    locked_year.semesters.update(is_current=False)
    if selected is not None:
        type(selected).objects.filter(pk=selected.pk).update(is_current=True)
    return locked_year
