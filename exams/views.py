import csv
from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Q, Value
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from academics.models import Enrollment, Grade, Section, Subject
from core.models import AcademicYear, Semester
from enterprise_ops.permissions import is_management, management_required
from enterprise_ops.services import audit, notify
from students.models import Student
from teachers.models import Teacher, TeacherAssignment

from .forms import ExamForm
from .mark_entry_service import build_mark_rows, resolve_mark_entry_scope, save_exam_marks
from .models import Exam, StudentMark
from .services import annual_report, dashboard_statistics, exam_statistics, student_academic_record


def _current_scope():
    year = AcademicYear.objects.filter(is_current=True, is_closed=False).first()
    if year is None:
        year = AcademicYear.objects.filter(is_closed=False).order_by("-start_date").first()
    semester = None
    if year:
        semester = year.semesters.filter(is_current=True).first() or year.semesters.order_by("code").first()
    return year, semester


def _selected_scope(request):
    current_year, current_semester = _current_scope()
    year_id = request.GET.get("academic_year") or (str(current_year.pk) if current_year else "")
    year = AcademicYear.objects.filter(pk=year_id).first() if year_id else None
    semester_id = request.GET.get("semester")
    if not semester_id and year:
        default_semester = year.semesters.filter(is_current=True).first() or year.semesters.order_by("code").first()
        semester_id = str(default_semester.pk) if default_semester else ""
    semester = Semester.objects.filter(pk=semester_id, academic_year=year).first() if semester_id and year else None
    return {
        "year": year,
        "semester": semester,
        "year_id": str(year.pk) if year else "",
        "semester_id": str(semester.pk) if semester else "",
        "grade_id": request.GET.get("grade", ""),
        "section_id": request.GET.get("section", ""),
        "subject_id": request.GET.get("subject", ""),
        "teacher_id": request.GET.get("teacher", ""),
    }


def _scope_filter_context(scope):
    year = scope["year"]
    grade_id = scope["grade_id"]
    sections = Section.objects.filter(is_active=True).select_related("grade", "academic_year")
    grades = Grade.objects.filter(is_active=True)
    subjects = Subject.objects.filter(is_active=True).select_related("grade")
    teachers = Teacher.objects.filter(is_active=True)
    if year:
        grades = grades.filter(school=year.school)
        sections = sections.filter(academic_year=year)
        teachers = teachers.filter(school=year.school)
    if grade_id:
        sections = sections.filter(grade_id=grade_id)
        subjects = subjects.filter(grade_id=grade_id)
    else:
        subjects = subjects.none()
    return {
        "academic_years": AcademicYear.objects.all().order_by("-start_date"),
        "semesters": year.semesters.all().order_by("code") if year else Semester.objects.none(),
        "grades": grades.order_by("order", "name"),
        "sections": sections.order_by("grade__order", "name"),
        "subjects": subjects.order_by("name"),
        "teachers": teachers.order_by("full_name"),
        "filters": scope,
    }


def _gradebook_rows(scope):
    year, semester = scope["year"], scope["semester"]
    section_id, subject_id = scope["section_id"], scope["subject_id"]
    if not all([year, semester, section_id, subject_id]):
        return [], {}, None
    section = Section.objects.filter(pk=section_id, academic_year=year, is_active=True).select_related("grade").first()
    subject = Subject.objects.filter(pk=subject_id, grade=section.grade if section else None, is_active=True).first()
    if not section or not subject:
        return [], {}, None
    assignment = TeacherAssignment.objects.filter(
        academic_year=year, section=section, subject=subject, is_active=True, teacher__is_active=True
    ).select_related("teacher", "section", "subject").first()
    exams = {
        item.exam_type: item
        for item in Exam.objects.filter(
            academic_year=year,
            semester=semester,
            section=section,
            subject=subject,
            is_active=True,
        ).select_related("teacher_assignment__teacher")
    }
    enrollments = Enrollment.objects.filter(
        academic_year=year, section=section, status="active"
    ).select_related("student").order_by("student__full_name")
    students = [item.student for item in enrollments]
    marks = defaultdict(dict)
    for item in StudentMark.objects.filter(
        exam_id__in=[exam.pk for exam in exams.values()], student__in=students
    ).select_related("exam"):
        marks[item.student_id][item.exam.exam_type] = item
    rows = []
    for student in students:
        cells = []
        total = Decimal("0.00")
        for exam_type, label in Exam.EXAM_TYPES:
            exam = exams.get(exam_type)
            mark = marks[student.pk].get(exam_type)
            value = Decimal(mark.mark) if mark else None
            if value is not None:
                total += value
            cells.append({"type": exam_type, "label": label, "exam": exam, "mark": mark, "value": value})
        rows.append({"student": student, "cells": cells, "total": total})
    return rows, exams, assignment


def _notify_management_exam_submitted(exam):
    teacher_name = exam.teacher_assignment.teacher.full_name if exam.teacher_assignment_id else "المعلم"
    recipients = []
    from django.contrib.auth import get_user_model
    User = get_user_model()
    for user in User.objects.filter(Q(is_superuser=True) | Q(is_staff=True), is_active=True).distinct():
        notify(
            user,
            "علامات امتحان بحاجة إلى مراجعة",
            f"{exam.get_exam_type_display()} لمادة {exam.subject.name} — {teacher_name} بحاجة إلى مراجعة واعتماد.",
            "warning",
            reverse("exams:exam_detail", args=[exam.pk]),
            event_key=f"exam-submitted:{exam.pk}:user:{user.pk}",
        )
        recipients.append(user.pk)
    return len(recipients)


def _notify_parents_exam_published(exam):
    students = Student.objects.filter(marks__exam=exam).distinct()
    sent = 0
    for student in students:
        users = {}
        for link in student.family_links.select_related("family__user").filter(is_active=True):
            if link.family.user_id:
                users[link.family.user_id] = link.family.user
        for user in users.values():
            notify(
                user,
                "تم نشر نتيجة جديدة",
                f"تم نشر نتيجة {exam.name} للطالب {student.full_name}.",
                "success",
                "/parent/marks/",
                event_key=f"exam:{exam.pk}:student:{student.pk}:user:{user.pk}",
            )
            sent += 1
    return sent


@management_required
def gradebook(request):
    scope = _selected_scope(request)
    rows, exams, assignment = _gradebook_rows(scope)
    pending_count = Exam.objects.filter(status="submitted").count()
    context = _scope_filter_context(scope)
    context.update({
        "rows": rows,
        "assessment_exams": exams,
        "assignment": assignment,
        "pending_count": pending_count,
        "scope_complete": bool(rows or all([scope["year"], scope["semester"], scope["section_id"], scope["subject_id"]])),
    })
    return render(request, "exams/gradebook.html", context)


@management_required
def exam_definitions(request):
    scope = _selected_scope(request)
    exams = Exam.objects.select_related(
        "academic_year", "semester", "grade", "section", "subject", "teacher_assignment__teacher"
    )
    if scope["year"]:
        exams = exams.filter(academic_year=scope["year"])
    if scope["semester"]:
        exams = exams.filter(semester=scope["semester"])
    for key in ("grade", "section", "subject"):
        value = scope[f"{key}_id"]
        if value:
            exams = exams.filter(**{f"{key}_id": value})
    context = _scope_filter_context(scope)
    context["exams"] = exams.order_by("grade__order", "section__name", "subject__name", "exam_type")
    return render(request, "exams/exam_list.html", context)


@management_required
def exam_dashboard(request):
    scope = _selected_scope(request)
    exams = Exam.objects.select_related(
        "academic_year", "semester", "grade", "section", "subject", "teacher_assignment__teacher"
    )
    if scope["year"]:
        exams = exams.filter(academic_year=scope["year"])
    if scope["semester"]:
        exams = exams.filter(semester=scope["semester"])
    for key in ("grade", "section", "subject"):
        value = scope[f"{key}_id"]
        if value:
            exams = exams.filter(**{f"{key}_id": value})
    if scope["teacher_id"]:
        exams = exams.filter(teacher_assignment__teacher_id=scope["teacher_id"])
    exams = exams.order_by("-exam_date", "name")
    stats = dashboard_statistics(exams)
    recent_exams = list(exams[:15])
    for exam in recent_exams:
        exam.analytics = exam_statistics(exam)

    normalized = ExpressionWrapper(
        F("mark") * Value(Decimal("100.00")) / F("exam__max_mark"),
        output_field=DecimalField(max_digits=7, decimal_places=2),
    )
    performance_qs = StudentMark.objects.filter(exam__in=exams).exclude(exam__teacher_assignment=None).annotate(
        normalized=normalized
    ).values(
        "exam__teacher_assignment__teacher_id",
        "exam__teacher_assignment__teacher__full_name",
        "exam__subject__name",
        "exam__section__name",
        "exam__grade__name",
    ).annotate(average=Avg("normalized"), results=Count("id")).order_by("-average")
    performance = []
    for row in performance_qs:
        avg = Decimal(row["average"] or 0)
        row["classification"] = "ممتاز" if avg >= 90 else "جيد جدًا" if avg >= 80 else "جيد" if avg >= 70 else "مقبول" if avg >= 60 else "بحاجة متابعة"
        performance.append(row)

    context = _scope_filter_context(scope)
    context.update({"stats": stats, "recent_exams": recent_exams, "teacher_performance": performance})
    return render(request, "exams/dashboard.html", context)


@management_required
@require_GET
def exam_scope_options(request):
    year_id = request.GET.get("academic_year")
    grade_id = request.GET.get("grade")
    section_id = request.GET.get("section")
    subject_id = request.GET.get("subject")
    semesters = Semester.objects.filter(academic_year_id=year_id).order_by("code") if year_id else Semester.objects.none()
    sections = Section.objects.filter(academic_year_id=year_id, grade_id=grade_id, is_active=True).order_by("name") if year_id and grade_id else Section.objects.none()
    subjects = Subject.objects.filter(grade_id=grade_id, is_active=True).order_by("name") if grade_id else Subject.objects.none()
    assignment = None
    if year_id and section_id and subject_id:
        assignment = TeacherAssignment.objects.filter(
            academic_year_id=year_id,
            section_id=section_id,
            subject_id=subject_id,
            is_active=True,
            teacher__is_active=True,
        ).select_related("teacher").first()
    return JsonResponse({
        "semesters": [{"id": item.pk, "label": item.get_code_display(), "current": item.is_current} for item in semesters],
        "sections": [{"id": item.pk, "label": str(item)} for item in sections],
        "subjects": [{"id": item.pk, "label": item.name} for item in subjects],
        "teacher": {"id": assignment.teacher_id, "name": assignment.teacher.full_name} if assignment else None,
    })


@management_required
def exam_create(request):
    initial = {}
    for field in ("academic_year", "semester", "grade", "section", "subject"):
        if request.GET.get(field):
            initial[field] = request.GET[field]
    form = ExamForm(request.POST or None, initial=initial)
    if form.is_valid():
        exam = form.save(commit=False)
        exam.status = "open"
        exam.is_locked = False
        exam.save()
        audit(request, "create", "exams.Exam", exam.pk, f"إنشاء امتحان وإتاحته للمعلم: {exam.name}")
        messages.success(request, f"تم إنشاء {exam.get_exam_type_display()} وإتاحته للمعلم {exam.teacher_assignment.teacher.full_name} لإدخال العلامات.")
        return redirect("exams:exam_detail", exam_id=exam.id)
    return render(request, "exams/exam_form.html", {"form": form, "title": "إضافة امتحان وإتاحته للمعلم"})


@management_required
def mark_create(request):
    messages.info(request, "العلامات تُدخل من الامتحان الذي أنشأته الإدارة فقط.")
    return redirect("exams:exam_list")


@management_required
def mark_list(request):
    marks = StudentMark.objects.select_related("student", "exam", "exam__subject", "exam__section").all()
    return render(request, "exams/mark_list.html", {"marks": marks})


@login_required
def exam_marks_bulk(request, exam_id):
    exam = get_object_or_404(
        Exam.objects.select_related("academic_year", "semester", "grade", "section", "subject", "teacher_assignment__teacher"),
        pk=exam_id,
    )
    assignment_id = request.GET.get("assignment") or request.POST.get("assignment") or exam.teacher_assignment_id
    assignment, students = resolve_mark_entry_scope(request.user, exam, assignment_id=assignment_id)
    if exam.teacher_assignment_id and assignment.pk != exam.teacher_assignment_id:
        messages.error(request, "هذا الامتحان مخصص لتكليف معلم آخر.")
        return redirect("teachers:portal_dashboard")
    if not exam.can_edit_marks:
        messages.error(request, "الامتحان مرسل للمراجعة أو معتمد أو مقفل ولا يمكن تعديل علاماته.")
        return redirect("teachers:portal_dashboard")

    if request.method == "POST":
        saved, errors = save_exam_marks(exam=exam, students=students, payload=request.POST, user=request.user)
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            action = request.POST.get("action", "submit")
            if action == "submit":
                marked_students = exam.marks.filter(student__in=students).values_list("student_id", flat=True).distinct().count()
                if marked_students != len(students):
                    messages.error(request, f"لا يمكن الإرسال قبل إدخال علامة لجميع الطلبة. المدخل {marked_students} من {len(students)}.")
                else:
                    exam.status = "submitted"
                    exam.submitted_by = request.user
                    exam.submitted_at = timezone.now()
                    exam.save(update_fields=["status", "submitted_by", "submitted_at"])
                    notified = _notify_management_exam_submitted(exam)
                    audit(request, "update", "exams.Exam", exam.pk, f"إرسال {exam.name} للإدارة للمراجعة")
                    messages.success(request, f"تم حفظ العلامات وإرسالها للإدارة للمراجعة. تم تنبيه {notified} من مسؤولي الإدارة.")
                    return redirect("teachers:portal_dashboard")
            else:
                audit(request, "update", "exams.Exam", exam.pk, f"حفظ {saved} علامة للامتحان {exam.name}")
                messages.success(request, f"تم حفظ {saved} علامة كمسودة عمل للمعلم.")
                return redirect(f"{reverse('exams:exam_marks_bulk', args=[exam.pk])}?assignment={assignment.pk}")

    return render(request, "exams/bulk_marks.html", {
        "exam": exam,
        "assignment": assignment,
        "rows": build_mark_rows(exam, students),
        "is_teacher_entry": True,
    })


@login_required
def exam_detail(request, exam_id):
    exam = get_object_or_404(
        Exam.objects.select_related(
            "academic_year", "semester", "grade", "section", "subject", "approved_by",
            "submitted_by", "teacher_assignment__teacher",
        ),
        pk=exam_id,
    )
    if not is_management(request.user):
        assignment = exam.teacher_assignment
        if assignment is None or assignment.teacher.user_id != request.user.pk:
            messages.error(request, "لا تملك التكليف التدريسي المرتبط بهذا الامتحان.")
            return redirect("teachers:portal_dashboard")
        return redirect(f"{reverse('exams:exam_marks_bulk', args=[exam.pk])}?assignment={assignment.pk}")
    analytics = exam_statistics(exam)
    return render(request, "exams/exam_detail.html", {"exam": exam, "marks": analytics.pop("marks"), "stats": analytics})


def _queue_exam_marks_for_openemis(exam, user):
    try:
        from openemis_integration.models import OpenEMISSyncLog
    except Exception:
        return 0
    queued = 0
    school = exam.academic_year.school
    for item in exam.marks.select_related("student").all():
        message = f"علامات الامتحان #{exam.pk} جاهزة للمزامنة."
        exists = OpenEMISSyncLog.objects.filter(
            school=school, student=item.student, operation="sync_marks", status="pending", message=message
        ).exists()
        if exists:
            continue
        OpenEMISSyncLog.objects.create(
            school=school,
            student=item.student,
            operation="sync_marks",
            status="pending",
            message=message,
            request_payload={
                "exam_id": exam.pk,
                "student_id": item.student_id,
                "mark": str(item.mark),
                "max_mark": str(exam.max_mark),
                "academic_year": exam.academic_year.name,
                "semester": exam.semester.code,
                "grade": exam.grade.name,
                "section": exam.section.name if exam.section_id else "",
                "subject": exam.subject.name,
                "exam_type": exam.exam_type,
            },
            created_by=user,
        )
        queued += 1
    return queued


@management_required
@require_POST
def exam_action(request, exam_id):
    exam = get_object_or_404(Exam, pk=exam_id)
    if exam.academic_year.is_closed:
        messages.error(request, "العام الدراسي مغلق ولا يمكن تغيير حالة امتحاناته.")
        return redirect("exams:exam_detail", exam_id=exam.id)
    action = request.POST.get("action")
    if action in {"approve", "publish"}:
        if exam.status != "submitted":
            messages.error(request, "لا يمكن الاعتماد قبل أن يرسل المعلم العلامات للإدارة للمراجعة.")
            return redirect("exams:exam_detail", exam_id=exam.id)
        if not exam.marks.exists():
            messages.error(request, "لا يمكن اعتماد امتحان دون علامات.")
            return redirect("exams:exam_detail", exam_id=exam.id)
        now = timezone.now()
        exam.status = "published"
        exam.is_locked = True
        exam.approved_by = request.user
        exam.approved_at = now
        exam.published_at = now
        exam.save(update_fields=["status", "is_locked", "approved_by", "approved_at", "published_at"])
        queued = _queue_exam_marks_for_openemis(exam, request.user)
        parent_notifications = _notify_parents_exam_published(exam)
        messages.success(request, f"تم الاعتماد والنشر لولي الأمر ({parent_notifications} إشعارًا) وتجهيز {queued} سجلًا لمزامنة OpenEMIS.")
    elif action == "return":
        exam.status = "open"
        exam.is_locked = False
        exam.submitted_at = None
        exam.submitted_by = None
        exam.save(update_fields=["status", "is_locked", "submitted_at", "submitted_by"])
        if exam.teacher_assignment_id and exam.teacher_assignment.teacher.user_id:
            notify(
                exam.teacher_assignment.teacher.user,
                "إعادة علامات امتحان للتعديل",
                f"أعادت الإدارة {exam.name} للتعديل. راجع العلامات ثم أرسلها مجددًا.",
                "warning",
                reverse("exams:exam_marks_bulk", args=[exam.pk]),
                event_key=f"exam-returned:{exam.pk}:{timezone.now().timestamp()}",
            )
        messages.success(request, "تمت إعادة الامتحان للمعلم للتعديل.")
    elif action == "reopen":
        exam.status = "open"
        exam.is_locked = False
        exam.approved_by = None
        exam.approved_at = None
        exam.published_at = None
        exam.submitted_by = None
        exam.submitted_at = None
        exam.save(update_fields=["status", "is_locked", "approved_by", "approved_at", "published_at", "submitted_by", "submitted_at"])
        messages.success(request, "تم فتح الامتحان للمعلم من جديد وإلغاء حالة النشر السابقة.")
    elif action == "close":
        exam.status = "closed"
        exam.is_locked = True
        exam.save(update_fields=["status", "is_locked"])
        messages.success(request, "تم إغلاق الامتحان.")
    else:
        messages.error(request, "الإجراء غير معروف.")
        return redirect("exams:exam_detail", exam_id=exam.id)
    audit(request, "update", "exams.Exam", exam.pk, f"إجراء {action} على الامتحان {exam.name}")
    return redirect("exams:exam_detail", exam_id=exam.id)
@management_required
def exam_export_csv(request, exam_id):
    exam = get_object_or_404(Exam, pk=exam_id)
    analytics = exam_statistics(exam)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="exam_{exam.id}_marks.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["الطالب", "رقم الطالب", "العلامة", "العلامة القصوى", "النسبة", "التقدير"])
    for mark in analytics["marks"]:
        writer.writerow([mark.student.full_name, mark.student.student_number, mark.mark, exam.max_mark, mark.percentage, mark.grade_letter])
    audit(request, "export", "exams.Exam", exam.pk, f"تصدير علامات {exam.name}")
    return response


@management_required
def student_record(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    return render(request, "exams/student_record.html", {"student": student, "record": student_academic_record(student)})


@management_required
def student_record_print(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    return render(request, "exams/student_record_print.html", {"student": student, "record": student_academic_record(student)})


@management_required
def exam_update(request, exam_id):
    exam = get_object_or_404(Exam, pk=exam_id)
    if exam.academic_year.is_closed:
        messages.error(request, "العام الدراسي مغلق ولا يمكن تعديل امتحاناته.")
        return redirect("exams:exam_detail", exam_id=exam.id)
    if exam.is_locked:
        messages.error(request, "الامتحان مقفل. افتحه أولًا قبل التعديل.")
        return redirect("exams:exam_detail", exam_id=exam.id)
    form = ExamForm(request.POST or None, instance=exam)
    if form.is_valid():
        form.save()
        audit(request, "update", "exams.Exam", exam.pk, f"تعديل امتحان: {exam.name}")
        messages.success(request, "تم تحديث الامتحان بنجاح.")
        return redirect("exams:exam_detail", exam_id=exam.id)
    return render(request, "exams/exam_form.html", {"form": form, "title": "تعديل امتحان"})


@management_required
def exam_delete(request, exam_id):
    exam = get_object_or_404(Exam, pk=exam_id)
    if exam.academic_year.is_closed:
        messages.error(request, "العام الدراسي مغلق ولا يمكن حذف امتحاناته التاريخية.")
        return redirect("exams:exam_detail", exam_id=exam.id)
    if exam.is_locked:
        messages.error(request, "لا يمكن حذف امتحان معتمد أو مقفل.")
        return redirect("exams:exam_detail", exam_id=exam.id)
    if request.method == "POST":
        name = exam.name
        exam.delete()
        audit(request, "delete", "exams.Exam", exam_id, f"حذف امتحان: {name}")
        messages.success(request, "تم حذف الامتحان.")
        return redirect("exams:exam_list")
    return render(request, "exams/exam_confirm_delete.html", {"exam": exam})


@management_required
def student_report_card(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    year_id = request.GET.get("year")
    if year_id:
        academic_year = get_object_or_404(AcademicYear, pk=year_id)
    else:
        enrollment = student.enrollments.select_related("academic_year").order_by("-academic_year__start_date").first()
        academic_year = enrollment.academic_year if enrollment else AcademicYear.objects.filter(is_current=True, is_closed=False).first()
    report = annual_report(student=student, academic_year=academic_year) if academic_year else None
    return render(request, "exams/student_report_card.html", {"student": student, "report": report})


@management_required
def issue_student_report_card(request, student_id):
    from documents.models import DocumentTemplate, IssuedDocument, StudentIssuedDocument
    from documents.utils import generate_document_number
    student = get_object_or_404(Student, pk=student_id)
    enrollment = student.enrollments.select_related("academic_year").order_by("-academic_year__start_date").first()
    if not enrollment:
        messages.error(request, "لا يوجد قيد دراسي للطالب لإصدار الشهادة.")
        return redirect("exams:student_report_card", student_id=student.id)
    report = annual_report(student=student, academic_year=enrollment.academic_year)
    if not report["complete"]:
        messages.error(request, "لا يمكن إصدار الشهادة قبل اكتمال علامات الفصلين.")
        return redirect("exams:student_report_card", student_id=student.id)
    number = generate_document_number()
    content = f"شهادة الطالب {student.full_name} - المعدل السنوي {report['annual_average']}%"
    template = DocumentTemplate.objects.filter(document_type="report_card", is_active=True).first()
    issued = IssuedDocument.objects.create(template=template, student=student, applicant_name=student.full_name, document_number=number, title="كشف علامات أكاديمي", content=content, issued_by=request.user)
    StudentIssuedDocument.objects.get_or_create(student=student, issued_document=issued)
    audit(request, "create", "documents.IssuedDocument", issued.pk, f"إصدار كشف علامات للطالب {student.full_name}")
    messages.success(request, f"تم إصدار كشف العلامات برقم {number}.")
    return redirect("documents:document_detail", document_id=issued.id)
