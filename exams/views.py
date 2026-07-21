import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from enterprise_ops.permissions import is_management, management_required
from enterprise_ops.services import audit, notify
from students.models import Student

from .forms import ExamForm
from .models import Exam, StudentMark
from .workflow import (
    build_exam_dashboard_context, build_exam_definitions_context, build_exam_detail_context,
    build_gradebook_context, build_mark_list_queryset, build_mark_rows, build_scope_options_payload,
    build_student_record_context, build_student_report_card_context, resolve_mark_entry_scope,
    resolve_report_year, save_exam_marks,
)


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
    return render(request, "exams/gradebook.html", build_gradebook_context(request))


@management_required
def exam_definitions(request):
    return render(request, "exams/exam_list.html", build_exam_definitions_context(request))

@management_required
def exam_dashboard(request):
    return render(request, "exams/dashboard.html", build_exam_dashboard_context(request))

@management_required
@require_GET
def exam_scope_options(request):
    return JsonResponse(build_scope_options_payload(
        year_id=request.GET.get("academic_year"),
        grade_id=request.GET.get("grade"),
        section_id=request.GET.get("section"),
        subject_id=request.GET.get("subject"),
    ))

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
    return render(request, "exams/mark_list.html", {"marks": build_mark_list_queryset()})


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
    return render(request, "exams/exam_detail.html", build_exam_detail_context(exam))


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
    analytics = build_exam_detail_context(exam)["stats"]
    analytics["marks"] = list(exam.marks.select_related("student").order_by("-mark", "student__full_name"))
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
    return render(request, "exams/student_record.html", build_student_record_context(student))


@management_required
def student_record_print(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    return render(request, "exams/student_record_print.html", build_student_record_context(student))


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
    return render(
        request,
        "exams/student_report_card.html",
        build_student_report_card_context(student, year_id=request.GET.get("year")),
    )


@management_required
def issue_student_report_card(request, student_id):
    from documents.models import DocumentTemplate, IssuedDocument, StudentIssuedDocument
    from documents.utils import generate_document_number
    student = get_object_or_404(Student, pk=student_id)
    enrollment = student.enrollments.select_related("academic_year").order_by("-academic_year__start_date").first()
    if not enrollment:
        messages.error(request, "لا يوجد قيد دراسي للطالب لإصدار الشهادة.")
        return redirect("exams:student_report_card", student_id=student.id)
    report = build_student_report_card_context(student, year_id=enrollment.academic_year_id)["report"]
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
