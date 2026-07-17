import csv
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import Grade, Subject
from core.models import AcademicYear
from enterprise_ops.permissions import is_management, management_required
from enterprise_ops.services import audit, notify
from students.models import Student

from .forms import ExamForm
from .models import Exam, StudentMark
from .services import annual_report, dashboard_statistics, exam_statistics, student_academic_record
from .mark_entry_service import build_mark_rows, resolve_mark_entry_scope, save_exam_marks


def _notify_parents_exam_published(exam):
    students = Student.objects.filter(marks__exam=exam).distinct()
    sent = 0
    for student in students:
        users = {}
        for link in student.family_links.select_related("family__user").filter(is_active=True):
            if link.family.user_id:
                users[link.family.user_id] = link.family.user
        for user in users.values():
            notify(user, "تم نشر نتيجة جديدة", f"تم نشر نتيجة {exam.name} للطالب {student.full_name}.", "success", "/parent/marks/")
            sent += 1
    return sent


@management_required
def exam_list(request):
    exams = Exam.objects.select_related("academic_year", "semester", "grade", "subject").all()
    return render(request, "exams/exam_list.html", {"exams": exams})


@management_required
def exam_dashboard(request):
    exams = Exam.objects.select_related("academic_year", "grade", "subject")
    academic_year_id = request.GET.get("academic_year")
    grade_id = request.GET.get("grade")
    subject_id = request.GET.get("subject")
    if academic_year_id:
        exams = exams.filter(academic_year_id=academic_year_id)
    if grade_id:
        exams = exams.filter(grade_id=grade_id)
    if subject_id:
        exams = exams.filter(subject_id=subject_id)
    exams = exams.order_by("-exam_date", "name")
    stats = dashboard_statistics(exams)
    recent_exams = list(exams[:10])
    for exam in recent_exams:
        exam.analytics = exam_statistics(exam)
    return render(request, "exams/dashboard.html", {
        "stats": stats,
        "recent_exams": recent_exams,
        "academic_years": AcademicYear.objects.all().order_by("-start_date"),
        "grades": Grade.objects.filter(is_active=True).order_by("order", "name"),
        "subjects": Subject.objects.filter(is_active=True).order_by("name"),
        "selected_academic_year": academic_year_id or "",
        "selected_grade": grade_id or "",
        "selected_subject": subject_id or "",
    })


@management_required
def exam_create(request):
    form = ExamForm(request.POST or None)
    if form.is_valid():
        exam = form.save()
        audit(request, "create", "exams.Exam", exam.pk, f"إنشاء امتحان: {exam.name}")
        messages.success(request, "تم إنشاء الامتحان بنجاح.")
        return redirect("exams:exam_detail", exam_id=exam.id)
    return render(request, "exams/exam_form.html", {"form": form, "title": "إضافة امتحان"})


@management_required
def mark_create(request):
    """Compatibility route: marks are entered only from an exam."""
    messages.info(request, "اختر الامتحان ثم استخدم نافذة إدخال العلامات الجماعية المعتمدة.")
    return redirect("exams:exam_list")


@management_required
def mark_list(request):
    marks = StudentMark.objects.select_related("student", "exam", "exam__subject").all()
    return render(request, "exams/mark_list.html", {"marks": marks})


@login_required
def exam_marks_bulk(request, exam_id):
    exam = get_object_or_404(
        Exam.objects.select_related("academic_year", "semester", "grade", "subject"),
        pk=exam_id,
    )
    assignment_id = request.GET.get("assignment") or request.POST.get("assignment")
    assignment, students = resolve_mark_entry_scope(request.user, exam, assignment_id=assignment_id)

    if not exam.can_edit_marks:
        messages.error(request, "الامتحان معتمد أو مقفل ولا يمكن تعديل علاماته.")
        return redirect("exams:exam_detail", exam_id=exam.id)

    if request.method == "POST":
        saved, errors = save_exam_marks(
            exam=exam,
            students=students,
            payload=request.POST,
            user=request.user,
        )
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            audit(request, "update", "exams.Exam", exam.pk, f"حفظ {saved} علامة للامتحان {exam.name}")
            messages.success(request, f"تم حفظ {saved} علامة بنجاح.")
            target = reverse("exams:exam_marks_bulk", args=[exam.pk])
            if assignment:
                target = f"{target}?assignment={assignment.pk}"
            return redirect(target)

    return render(
        request,
        "exams/bulk_marks.html",
        {
            "exam": exam,
            "assignment": assignment,
            "rows": build_mark_rows(exam, students),
            "is_teacher_entry": assignment is not None,
        },
    )


@login_required
def exam_detail(request, exam_id):
    exam = get_object_or_404(
        Exam.objects.select_related("academic_year", "semester", "grade", "subject", "approved_by"),
        pk=exam_id,
    )
    if not is_management(request.user):
        teacher = getattr(request.user, "teacher_profile", None)
        assignment = None
        if teacher is not None and teacher.is_active:
            assignment = teacher.assignments.filter(
                is_active=True,
                academic_year=exam.academic_year,
                subject=exam.subject,
                section__grade=exam.grade,
            ).order_by("pk").first()
        if assignment is None:
            messages.error(request, "لا تملك تكليفًا تدريسيًا فعالًا لهذا الامتحان.")
            return redirect("teachers:portal_dashboard")
        target = reverse("exams:exam_marks_bulk", args=[exam.pk])
        return redirect(f"{target}?assignment={assignment.pk}")
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
            school=school,
            student=item.student,
            operation="sync_marks",
            status="pending",
            message=message,
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
        _notify_parents_exam_published(exam)
        messages.success(request, f"تم اعتماد العلامات وإتاحتها لولي الأمر وتجهيز {queued} سجلًا لمزامنة OpenEMIS.")
    elif action == "reopen":
        exam.status = "open"
        exam.is_locked = False
        exam.approved_by = None
        exam.approved_at = None
        exam.published_at = None
        exam.save(update_fields=["status", "is_locked", "approved_by", "approved_at", "published_at"])
    elif action == "close":
        exam.status = "closed"
        exam.is_locked = True
        exam.save(update_fields=["status", "is_locked"])
    else:
        messages.error(request, "الإجراء غير معروف.")
        return redirect("exams:exam_detail", exam_id=exam.id)
    audit(request, "update", "exams.Exam", exam.pk, f"إجراء {action} على الامتحان {exam.name}")
    messages.success(request, "تم تحديث حالة الامتحان.")
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
