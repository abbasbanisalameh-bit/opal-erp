"""Exam-cycle distribution and academic result closure services."""

from collections import Counter, defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from academics.models import Enrollment
from teachers.models import TeacherAssignment

from .models import (
    AnnualStudentResult,
    AnnualSubjectResult,
    Exam,
    ExamCycle,
    SemesterSubjectResult,
)


ZERO = Decimal("0.00")
EXAM_TYPES = tuple(code for code, _label in Exam.EXAM_TYPES)
FINAL_EXAM_STATUSES = {"published", "closed"}
EXAM_SEQUENCE = ("first", "second", "third", "final")
EXAM_PREDECESSOR = {
    "second": "first",
    "third": "second",
    "final": "third",
}


def _active_assignments(year):
    return TeacherAssignment.objects.filter(
        academic_year=year,
        is_active=True,
        teacher__is_active=True,
        section__is_active=True,
        subject__is_active=True,
    ).select_related("teacher", "section__grade", "subject")


def exam_cycle_completion_report(*, academic_year, semester, exam_type):
    """Return objective blockers and metrics for one required exam cycle."""
    assignments = list(_active_assignments(academic_year))
    expected_keys = {(item.section_id, item.subject_id) for item in assignments}
    exams = list(
        Exam.objects.filter(
            academic_year=academic_year,
            semester=semester,
            exam_type=exam_type,
            is_active=True,
            section__isnull=False,
        )
        .select_related("section__grade", "subject")
        .prefetch_related("marks")
    )
    exam_by_key = {(exam.section_id, exam.subject_id): exam for exam in exams}
    missing_keys = expected_keys.difference(exam_by_key)
    unfinished = [
        exam for key, exam in exam_by_key.items()
        if key in expected_keys and exam.status not in FINAL_EXAM_STATUSES
    ]

    missing_marks = 0
    affected_exams = []
    for key in expected_keys.intersection(exam_by_key):
        exam = exam_by_key[key]
        expected_students = set(
            Enrollment.objects.filter(
                academic_year=academic_year,
                section_id=exam.section_id,
                status="active",
            ).values_list("student_id", flat=True)
        )
        marked_students = set(
            exam.marks.filter(student_id__in=expected_students)
            .values_list("student_id", flat=True)
        )
        missing = len(expected_students.difference(marked_students))
        if missing:
            missing_marks += missing
            affected_exams.append((exam, missing))

    cycle_exists = ExamCycle.objects.filter(
        academic_year=academic_year, semester=semester, exam_type=exam_type
    ).exists()
    blockers = []
    if not cycle_exists:
        blockers.append(f"لم تُفتح دورة {dict(Exam.EXAM_TYPES)[exam_type]} بعد.")
    if not assignments and Enrollment.objects.filter(academic_year=academic_year, status="active").exists():
        blockers.append("لا توجد تكليفات تدريسية فعالة لبناء دورة امتحانية مكتملة.")
    if missing_keys:
        blockers.append(f"ينقص تعريف {len(missing_keys)} امتحانًا للتكليفات الفعالة.")
    if unfinished:
        blockers.append(f"يوجد {len(unfinished)} امتحانًا لم يعتمد وينشر بعد.")
    if missing_marks:
        blockers.append(
            f"يوجد {missing_marks} علامة طالب ناقصة موزعة على {len(affected_exams)} امتحانًا."
        )
    return {
        "complete": not blockers,
        "blockers": blockers,
        "metrics": {
            "assignments": len(assignments),
            "expected_exams": len(expected_keys),
            "defined_exams": len(expected_keys.intersection(exam_by_key)),
            "missing_definitions": len(missing_keys),
            "unfinished_exams": len(unfinished),
            "missing_marks": missing_marks,
        },
    }


def validate_exam_cycle_opening(*, academic_year, semester, exam_type):
    """Enforce the official sequential assessment workflow."""
    if exam_type not in EXAM_SEQUENCE:
        raise ValidationError("نوع الدورة الامتحانية غير معتمد.")
    if semester.academic_year_id != academic_year.pk:
        raise ValidationError("الفصل الدراسي لا يتبع العام المحدد.")
    if semester.code == "second":
        first_semester = academic_year.semesters.filter(code="first").first()
        if first_semester is None or not first_semester.is_closed:
            raise ValidationError(
                "لا يمكن تشغيل امتحانات الفصل الثاني قبل إغلاق الفصل الدراسي الأول أكاديميًا."
            )
    predecessor = EXAM_PREDECESSOR.get(exam_type)
    if predecessor is None:
        return None
    report = exam_cycle_completion_report(
        academic_year=academic_year, semester=semester, exam_type=predecessor
    )
    if report["blockers"]:
        previous_label = dict(Exam.EXAM_TYPES)[predecessor]
        current_label = dict(Exam.EXAM_TYPES)[exam_type]
        raise ValidationError([
            f"لا يمكن فتح {current_label} قبل اكتمال {previous_label} بالكامل.",
            *report["blockers"],
        ])
    return report


@transaction.atomic
def open_exam_cycle(*, academic_year, semester, exam_type, user=None, name="", notes=""):
    """Open one cycle and distribute exam definitions to all live assignments."""
    if academic_year.is_closed:
        raise ValidationError("العام الدراسي مغلق ولا يقبل دورة امتحانية جديدة.")
    if semester.academic_year_id != academic_year.pk:
        raise ValidationError("الفصل الدراسي لا يتبع العام المحدد.")
    if semester.is_closed:
        raise ValidationError("الفصل الدراسي مغلق أكاديميًا.")
    if exam_type not in dict(Exam.EXAM_TYPES):
        raise ValidationError("نوع الدورة الامتحانية غير معتمد.")

    validate_exam_cycle_opening(
        academic_year=academic_year, semester=semester, exam_type=exam_type
    )

    assignments = list(_active_assignments(academic_year))
    duplicate_keys = [
        key
        for key, count in Counter(
            (item.section_id, item.subject_id) for item in assignments
        ).items()
        if count > 1
    ]
    if duplicate_keys:
        raise ValidationError(
            f"يوجد {len(duplicate_keys)} تكليف مكرر للمادة والشعبة. صحح التكليفات قبل فتح الدورة."
        )

    cycle, cycle_created = ExamCycle.objects.select_for_update().get_or_create(
        academic_year=academic_year,
        semester=semester,
        exam_type=exam_type,
        defaults={
            "name": (name or "").strip(),
            "notes": (notes or "").strip(),
            "opened_by": user if getattr(user, "is_authenticated", False) else None,
            "status": "open",
        },
    )
    if cycle.status == "closed":
        raise ValidationError("هذه الدورة مغلقة. أعد فتح الفصل والامتحانات بصلاحية المدير أولًا.")

    created_count = linked_count = 0
    for assignment in assignments:
        lookup = {
            "academic_year": academic_year,
            "semester": semester,
            "section": assignment.section,
            "grade": assignment.section.grade,
            "subject": assignment.subject,
            "exam_type": exam_type,
        }
        exam = Exam.objects.filter(**lookup).first()
        if exam is None:
            Exam.objects.create(
                **lookup,
                cycle=cycle,
                teacher_assignment=assignment,
                status="open",
                is_locked=False,
                is_active=True,
            )
            created_count += 1
        else:
            updates = {}
            if exam.cycle_id is None:
                updates["cycle"] = cycle
            if exam.teacher_assignment_id is None:
                updates["teacher_assignment"] = assignment
            if exam.status == "draft" and not exam.is_locked:
                updates["status"] = "open"
            if updates:
                for field, value in updates.items():
                    setattr(exam, field, value)
                exam.save(update_fields=list(updates))
                linked_count += 1
    return cycle, {
        "cycle_created": cycle_created,
        "assignments": len(assignments),
        "exams_created": created_count,
        "legacy_exams_linked": linked_count,
    }


def semester_closure_report(semester):
    year = semester.academic_year
    assignments = list(_active_assignments(year))
    exams = list(
        Exam.objects.filter(academic_year=year, semester=semester, is_active=True)
        .select_related("section", "subject", "teacher_assignment")
        .prefetch_related("marks")
    )
    exam_by_key = {
        (exam.section_id, exam.subject_id, exam.exam_type): exam
        for exam in exams
        if exam.section_id
    }
    expected_keys = {
        (assignment.section_id, assignment.subject_id, exam_type)
        for assignment in assignments
        for exam_type in EXAM_TYPES
    }
    missing_definitions = expected_keys.difference(exam_by_key)
    unfinished = [exam for key, exam in exam_by_key.items() if key in expected_keys and exam.status not in FINAL_EXAM_STATUSES]
    missing_marks = 0
    affected_exams = 0
    for key in expected_keys.intersection(exam_by_key):
        exam = exam_by_key[key]
        expected_students = set(
            Enrollment.objects.filter(
                academic_year=year,
                section_id=exam.section_id,
                status="active",
            ).values_list("student_id", flat=True)
        )
        marked_students = set(exam.marks.filter(student_id__in=expected_students).values_list("student_id", flat=True))
        missing = len(expected_students.difference(marked_students))
        if missing:
            affected_exams += 1
            missing_marks += missing

    blockers = []
    if semester.is_closed:
        blockers.append("الفصل الدراسي مغلق بالفعل.")
    if not assignments and Enrollment.objects.filter(academic_year=year, status="active").exists():
        blockers.append("لا توجد تكليفات تدريسية فعالة لبناء دورة نتائج مكتملة.")
    if missing_definitions:
        blockers.append(f"ينقص تعريف {len(missing_definitions)} امتحانًا مطلوبًا للتكليفات الفعالة.")
    if unfinished:
        blockers.append(f"يوجد {len(unfinished)} امتحانًا لم يعتمد وينشر بعد.")
    if missing_marks:
        blockers.append(f"يوجد {missing_marks} علامة طالب ناقصة موزعة على {affected_exams} امتحانًا.")
    return {
        "blockers": blockers,
        "metrics": {
            "assignments": len(assignments),
            "expected_exams": len(expected_keys),
            "defined_exams": len(expected_keys.intersection(exam_by_key)),
            "missing_definitions": len(missing_definitions),
            "unfinished_exams": len(unfinished),
            "missing_marks": missing_marks,
        },
    }


def _calculate_semester_results(semester):
    year = semester.academic_year
    exams = Exam.objects.filter(
        academic_year=year,
        semester=semester,
        status__in=FINAL_EXAM_STATUSES,
        section__isnull=False,
    ).select_related("subject", "section").prefetch_related("marks")
    marks = defaultdict(lambda: ZERO)
    for exam in exams:
        for item in exam.marks.all():
            marks[(item.student_id, exam.subject_id)] += item.mark

    updated = 0
    for (student_id, subject_id), score in marks.items():
        SemesterSubjectResult.objects.update_or_create(
            semester=semester,
            student_id=student_id,
            subject_id=subject_id,
            defaults={"score": score.quantize(Decimal("0.01"))},
        )
        updated += 1
    return updated


@transaction.atomic
def close_semester(*, semester, user=None, notes=""):
    from core.models import Semester
    from academics.semester_structure import finalize_and_seed_next_semester

    semester = Semester.objects.select_for_update().select_related("academic_year").get(pk=semester.pk)
    if semester.is_closed:
        return semester, {"already_closed": True, "results": semester.subject_results.count()}
    report = semester_closure_report(semester)
    if report["blockers"]:
        raise ValidationError(report["blockers"])

    results = _calculate_semester_results(semester)
    exams = Exam.objects.filter(academic_year=semester.academic_year, semester=semester)
    closed_exams = exams.filter(status="published").update(status="closed", is_locked=True)
    for cycle in ExamCycle.objects.filter(academic_year=semester.academic_year, semester=semester):
        if not cycle.exams.exclude(status="closed", is_locked=True).exists():
            cycle.status = "closed"
            cycle.closed_at = timezone.now()
            cycle.save(update_fields=["status", "closed_at"])
    semester.is_closed = True
    semester.is_current = False
    semester.closed_at = timezone.now()
    semester.closed_by = user if getattr(user, "is_authenticated", False) else None
    semester.closure_notes = (notes or "").strip()
    semester.save(update_fields=["is_closed", "is_current", "closed_at", "closed_by", "closure_notes"])
    structure_snapshot = finalize_and_seed_next_semester(semester=semester, user=user)
    annual_results = None
    if not semester.academic_year.semesters.filter(is_closed=False).exists():
        annual_results = calculate_annual_results(semester.academic_year)
    return semester, {
        "already_closed": False,
        "results": results,
        "closed_exams": closed_exams,
        "annual_results": annual_results,
        "structure_snapshot": structure_snapshot.pk,
    }


@transaction.atomic
def reopen_semester(*, semester, user=None, reason=""):
    from core.models import Semester

    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("سبب إعادة فتح الفصل إلزامي.")
    semester = Semester.objects.select_for_update().select_related("academic_year").get(pk=semester.pk)
    if semester.academic_year.is_closed:
        raise ValidationError("لا يمكن إعادة فتح فصل داخل عام مغلق أكاديميًا.")
    if not semester.is_closed:
        raise ValidationError("الفصل الدراسي مفتوح أصلًا.")
    if semester.academic_year.semesters.filter(
        start_date__gt=semester.start_date,
        is_closed=True,
    ).exists():
        raise ValidationError("أعد فتح الفصل اللاحق أولًا للمحافظة على ترتيب النتائج التاريخية.")
    semester.is_closed = False
    semester.closed_at = None
    semester.closed_by = None
    semester.closure_notes = f"أعيد فتح الفصل: {reason}"
    semester.save(update_fields=["is_closed", "closed_at", "closed_by", "closure_notes"])
    ExamCycle.objects.filter(academic_year=semester.academic_year, semester=semester, status="closed").update(
        status="open",
        closed_at=None,
    )
    Exam.objects.filter(
        academic_year=semester.academic_year,
        semester=semester,
        status="closed",
    ).update(
        status="open",
        is_locked=False,
        approved_by=None,
        approved_at=None,
        published_at=None,
        submitted_by=None,
        submitted_at=None,
    )
    SemesterSubjectResult.objects.filter(semester=semester).delete()
    AnnualSubjectResult.objects.filter(academic_year=semester.academic_year).delete()
    AnnualStudentResult.objects.filter(academic_year=semester.academic_year).delete()
    try:
        snapshot = semester.structure_snapshot
    except Exception:
        snapshot = None
    if snapshot is not None:
        snapshot.is_final = False
        snapshot.captured_by = user if getattr(user, "is_authenticated", False) else None
        snapshot.save(update_fields=["is_final", "captured_by", "captured_at"])
    return semester


@transaction.atomic
def calculate_annual_results(academic_year):
    semesters = {item.code: item for item in academic_year.semesters.all()}
    if set(semesters) != {"first", "second"} or not all(item.is_closed for item in semesters.values()):
        raise ValidationError("يجب إغلاق الفصلين أكاديميًا قبل حساب النتائج السنوية.")

    first = {
        (item.student_id, item.subject_id): item.score
        for item in SemesterSubjectResult.objects.filter(semester=semesters["first"])
    }
    second = {
        (item.student_id, item.subject_id): item.score
        for item in SemesterSubjectResult.objects.filter(semester=semesters["second"])
    }
    if set(first) != set(second):
        missing_first = len(set(second).difference(first))
        missing_second = len(set(first).difference(second))
        raise ValidationError(
            f"نتائج الفصلين غير متطابقة: {missing_first} نتيجة بلا فصل أول و{missing_second} بلا فصل ثانٍ."
        )

    scores_by_student = defaultdict(list)
    subject_rows = 0
    for (student_id, subject_id), first_score in first.items():
        second_score = second[(student_id, subject_id)]
        annual_score = ((first_score + second_score) / Decimal("2")).quantize(Decimal("0.01"))
        AnnualSubjectResult.objects.update_or_create(
            academic_year=academic_year,
            student_id=student_id,
            subject_id=subject_id,
            defaults={
                "first_semester_score": first_score,
                "second_semester_score": second_score,
                "annual_score": annual_score,
            },
        )
        scores_by_student[student_id].append(annual_score)
        subject_rows += 1

    student_rows = 0
    for student_id, scores in scores_by_student.items():
        general = (sum(scores, ZERO) / Decimal(len(scores))).quantize(Decimal("0.01"))
        AnnualStudentResult.objects.update_or_create(
            academic_year=academic_year,
            student_id=student_id,
            defaults={"general_average": general, "subject_count": len(scores)},
        )
        student_rows += 1
    return {"subject_results": subject_rows, "student_results": student_rows}
