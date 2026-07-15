import csv
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import Enrollment, Grade, Subject
from core.models import AcademicYear
from enterprise_ops.services import audit, notify
from students.models import Student

from .forms import ExamForm, StudentMarkForm
from .models import Exam, StudentMark
from .services import annual_report, dashboard_statistics, exam_statistics, student_academic_record


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


@staff_member_required
def exam_list(request):
    exams = Exam.objects.select_related("academic_year", "semester", "grade", "subject").all()
    return render(request, "exams/exam_list.html", {"exams": exams})


@staff_member_required
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


@staff_member_required
def exam_create(request):
    form = ExamForm(request.POST or None)
    if form.is_valid():
        exam = form.save()
        audit(request, "create", "exams.Exam", exam.pk, f"إنشاء امتحان: {exam.name}")
        messages.success(request, "تم إنشاء الامتحان بنجاح.")
        return redirect("exams:exam_detail", exam_id=exam.id)
    return render(request, "exams/exam_form.html", {"form": form, "title": "إضافة امتحان"})


@staff_member_required
def mark_create(request):
    form = StudentMarkForm(request.POST or None)
    if form.is_valid():
        mark = form.save(commit=False)
        mark.entered_by = request.user
        mark.updated_by = request.user
        mark.full_clean()
        mark.save()
        audit(request, "create", "exams.StudentMark", mark.pk, f"إدخال علامة {mark.student} في {mark.exam}")
        messages.success(request, "تم حفظ العلامة بنجاح.")
        return redirect("exams:mark_list")
    return render(request, "exams/mark_form.html", {"form": form, "title": "إدخال علامة"})


@staff_member_required
def mark_list(request):
    marks = StudentMark.objects.select_related("student", "exam", "exam__subject").all()
    return render(request, "exams/mark_list.html", {"marks": marks})


@staff_member_required
def exam_marks_bulk(request, exam_id):
    exam = get_object_or_404(Exam, pk=exam_id)
    if not exam.can_edit_marks:
        messages.error(request, "الامتحان معتمد أو مقفل ولا يمكن تعديل علاماته.")
        return redirect("exams:exam_detail", exam_id=exam.id)
    enrollments = Enrollment.objects.filter(grade=exam.grade, academic_year=exam.academic_year, status="active").select_related("student")
    students = [enrollment.student for enrollment in enrollments]
    existing = {mark.student_id: mark.mark for mark in StudentMark.objects.filter(exam=exam)}
    if request.method == "POST":
        errors, parsed = [], {}
        max_mark = Decimal(exam.max_mark)
        for student in students:
            raw_value = request.POST.get(f"mark_{student.id}", "").strip()
            if not raw_value:
                continue
            try:
                value = Decimal(raw_value)
            except InvalidOperation:
                errors.append(f"علامة {student.full_name} غير صالحة.")
                continue
            if value < 0 or value > max_mark:
                errors.append(f"علامة {student.full_name} يجب أن تكون بين 0 و{exam.max_mark}.")
                continue
            parsed[student.id] = value
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            for student in students:
                if student.id not in parsed:
                    continue
                mark, created = StudentMark.objects.update_or_create(
                    exam=exam,
                    student=student,
                    defaults={"mark": parsed[student.id], "updated_by": request.user},
                )
                if created:
                    mark.entered_by = request.user
                    mark.save(update_fields=["entered_by"])
            if exam.status == "draft":
                exam.status = "open"
                exam.save(update_fields=["status"])
            audit(request, "update", "exams.Exam", exam.pk, f"حفظ علامات الامتحان {exam.name}")
            messages.success(request, "تم حفظ علامات الامتحان بنجاح.")
            return redirect("exams:exam_detail", exam_id=exam.id)
    return render(request, "exams/bulk_marks.html", {"exam": exam, "students": students, "existing": existing})


@staff_member_required
def exam_detail(request, exam_id):
    exam = get_object_or_404(Exam.objects.select_related("academic_year", "semester", "grade", "subject", "approved_by"), pk=exam_id)
    analytics = exam_statistics(exam)
    return render(request, "exams/exam_detail.html", {"exam": exam, "marks": analytics.pop("marks"), "stats": analytics})


@staff_member_required
@require_POST
def exam_action(request, exam_id):
    exam = get_object_or_404(Exam, pk=exam_id)
    action = request.POST.get("action")
    if action == "approve":
        if not exam.marks.exists():
            messages.error(request, "لا يمكن اعتماد امتحان دون علامات.")
            return redirect("exams:exam_detail", exam_id=exam.id)
        exam.status = "approved"
        exam.is_locked = True
        exam.approved_by = request.user
        exam.approved_at = timezone.now()
        exam.save(update_fields=["status", "is_locked", "approved_by", "approved_at"])
    elif action == "publish":
        if exam.status not in {"approved", "published"}:
            messages.error(request, "يجب اعتماد الامتحان قبل نشره.")
            return redirect("exams:exam_detail", exam_id=exam.id)
        exam.status = "published"
        exam.is_locked = True
        exam.published_at = timezone.now()
        exam.save(update_fields=["status", "is_locked", "published_at"])
        _notify_parents_exam_published(exam)
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


@staff_member_required
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


@staff_member_required
def student_record(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    return render(request, "exams/student_record.html", {"student": student, "record": student_academic_record(student)})


@staff_member_required
def student_record_print(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    return render(request, "exams/student_record_print.html", {"student": student, "record": student_academic_record(student)})


@staff_member_required
def exam_update(request, exam_id):
    exam = get_object_or_404(Exam, pk=exam_id)
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


@staff_member_required
def exam_delete(request, exam_id):
    exam = get_object_or_404(Exam, pk=exam_id)
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


@staff_member_required
def student_report_card(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    year_id = request.GET.get("year")
    if year_id:
        academic_year = get_object_or_404(AcademicYear, pk=year_id)
    else:
        enrollment = student.enrollments.select_related("academic_year").order_by("-academic_year__start_date").first()
        academic_year = enrollment.academic_year if enrollment else AcademicYear.objects.filter(is_current=True).first()
    report = annual_report(student=student, academic_year=academic_year) if academic_year else None
    return render(request, "exams/student_report_card.html", {"student": student, "report": report})


@staff_member_required
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
