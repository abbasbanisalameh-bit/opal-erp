from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import HomeworkForm, TeacherAccountCreateForm, TeacherAssignmentForm, TeacherForm
from .models import Homework, Teacher, TeacherAssignment
from academics.models import Section, Subject
from .account_services import create_teacher_account, reset_teacher_password
from enterprise_ops.permissions import management_required
from parent_portal.notification_services import notify_guardian_for_student
from timetable.live_services import teacher_live_status


@management_required
def dashboard(request):
    teachers = Teacher.objects.select_related("school", "branch").annotate(
        assignments_count=Count("assignments", filter=Q(assignments__is_active=True), distinct=True)
    )
    context = {
        "teachers_count": teachers.count(),
        "active_count": teachers.filter(is_active=True).count(),
        "assignments_count": TeacherAssignment.objects.filter(is_active=True).count(),
        "unassigned_count": teachers.filter(assignments_count=0).count(),
        "recent_teachers": teachers.order_by("-created_at")[:8],
    }
    return render(request, "teachers/dashboard.html", context)


@management_required
def teacher_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    teachers = Teacher.objects.select_related("school", "branch").annotate(
        assignments_count=Count("assignments", filter=Q(assignments__is_active=True), distinct=True)
    )
    if query:
        teachers = teachers.filter(
            Q(full_name__icontains=query) | Q(employee_number__icontains=query) |
            Q(phone__icontains=query) | Q(specialization__icontains=query)
        )
    if status == "active":
        teachers = teachers.filter(is_active=True)
    elif status == "inactive":
        teachers = teachers.filter(is_active=False)
    return render(request, "teachers/teacher_list.html", {"teachers": teachers, "query": query, "status": status})


@management_required
def teacher_create(request):
    form = TeacherForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        teacher = form.save()
        messages.success(request, "تمت إضافة المعلم بنجاح.")
        return redirect("teachers:teacher_detail", pk=teacher.pk)
    return render(request, "teachers/teacher_form.html", {"form": form, "title": "إضافة معلم"})


@management_required
def teacher_update(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    form = TeacherForm(request.POST or None, request.FILES or None, instance=teacher)
    if form.is_valid():
        form.save()
        messages.success(request, "تم تحديث بيانات المعلم.")
        return redirect("teachers:teacher_detail", pk=teacher.pk)
    return render(request, "teachers/teacher_form.html", {"form": form, "title": "تعديل بيانات المعلم", "teacher": teacher})


@management_required
def teacher_detail(request, pk):
    teacher = get_object_or_404(Teacher.objects.select_related("school", "branch"), pk=pk)
    assignments = teacher.assignments.select_related("academic_year", "section", "section__grade", "subject")
    timetable_entries = []
    try:
        timetable_entries = teacher.timetableentry_set.select_related("academic_year", "section", "subject", "time_slot").filter(is_active=True)
    except Exception:
        pass
    return render(request, "teachers/teacher_detail.html", {
        "teacher": teacher, "assignments": assignments, "timetable_entries": timetable_entries,
        "teacher_documents": teacher.documents.all(),
        "issued_documents": teacher.issued_documents.select_related("template").all(),
    })


@management_required
def teacher_toggle(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    if request.method == "POST":
        teacher.is_active = not teacher.is_active
        teacher.save(update_fields=["is_active"])
        if teacher.user_id and teacher.user.is_active != teacher.is_active:
            teacher.user.is_active = teacher.is_active
            teacher.user.save(update_fields=["is_active"])
        messages.success(request, "تم تحديث حالة المعلم.")
    return redirect("teachers:teacher_detail", pk=teacher.pk)


@management_required
def assignment_create(request, teacher_pk):
    teacher = get_object_or_404(Teacher, pk=teacher_pk)
    form = TeacherAssignmentForm(request.POST or None, teacher=teacher)
    if form.is_valid():
        assignment = form.save(commit=False)
        assignment.teacher = teacher
        assignment.save()
        messages.success(request, "تم حفظ التكليف التدريسي.")
        return redirect("teachers:teacher_detail", pk=teacher.pk)
    return render(request, "teachers/assignment_form.html", {"form": form, "teacher": teacher, "title": "إضافة تكليف تدريسي"})


@management_required
def assignment_update(request, pk):
    assignment = get_object_or_404(TeacherAssignment.objects.select_related("teacher"), pk=pk)
    if assignment.academic_year.is_closed:
        messages.error(request, "العام الدراسي مغلق ولا يمكن تعديل تكليفاته التاريخية.")
        return redirect("teachers:teacher_detail", pk=assignment.teacher_id)
    form = TeacherAssignmentForm(request.POST or None, instance=assignment, teacher=assignment.teacher)
    if form.is_valid():
        form.save()
        messages.success(request, "تم تحديث التكليف التدريسي.")
        return redirect("teachers:teacher_detail", pk=assignment.teacher_id)
    return render(request, "teachers/assignment_form.html", {"form": form, "teacher": assignment.teacher, "title": "تعديل التكليف التدريسي"})


@management_required
def assignment_delete(request, pk):
    assignment = get_object_or_404(TeacherAssignment, pk=pk)
    teacher_id = assignment.teacher_id
    if request.method == "POST":
        if assignment.academic_year.is_closed:
            messages.error(request, "العام الدراسي مغلق ولا يمكن حذف تكليفاته التاريخية.")
        else:
            assignment.delete()
            messages.success(request, "تم حذف التكليف التدريسي.")
    return redirect("teachers:teacher_detail", pk=teacher_id)



@management_required
def teacher_account_create(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    if teacher.user_id:
        messages.info(request, "المعلم مرتبط بحساب مستخدم بالفعل.")
        return redirect("teachers:teacher_detail", pk=teacher.pk)
    form = TeacherAccountCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            user, password = create_teacher_account(teacher, form.cleaned_data.get("username", ""))
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            return render(request, "teachers/account_credentials.html", {
                "teacher": teacher, "username": user.username, "password": password, "created": True,
            })
    return render(request, "teachers/account_form.html", {"teacher": teacher, "form": form})


@management_required
def teacher_account_reset(request, pk):
    teacher = get_object_or_404(Teacher.objects.select_related("user"), pk=pk)
    if not teacher.user_id:
        messages.error(request, "لا يوجد حساب مستخدم مرتبط بهذا المعلم.")
        return redirect("teachers:teacher_detail", pk=teacher.pk)
    if request.method != "POST":
        return redirect("teachers:teacher_detail", pk=teacher.pk)
    password = reset_teacher_password(teacher)
    return render(request, "teachers/account_credentials.html", {
        "teacher": teacher, "username": teacher.user.username, "password": password, "created": False,
    })

from django.forms import formset_factory
from django import forms
from django.utils import timezone
from academics.models import Enrollment
from attendance_v2.models import Attendance
from exams.models import Exam
from timetable.models import TimetableEntry
from .permissions import teacher_required


@teacher_required
def portal_dashboard(request):
    teacher = request.user.teacher_profile
    assignments = teacher.assignments.filter(is_active=True).select_related(
        "academic_year", "section", "section__grade", "subject"
    )
    timetable = TimetableEntry.objects.filter(teacher=teacher, is_active=True).select_related(
        "section", "subject", "time_slot"
    )
    homeroom_sections = teacher.homeroom_sections.filter(is_active=True).select_related(
        "academic_year", "grade"
    )
    latest_homework = Homework.objects.filter(
        assignment__teacher=teacher, is_active=True
    ).select_related("assignment__subject", "assignment__section")[:10]
    return render(request, "teachers/portal_dashboard.html", {
        "teacher": teacher,
        "assignments": assignments,
        "timetable": timetable,
        "homeroom_sections": homeroom_sections,
        "latest_homework": latest_homework,
        "live_status": teacher_live_status(teacher),
    })


@teacher_required
def portal_timetable(request):
    """Filtered timetable for the authenticated teacher only."""
    teacher = request.user.teacher_profile
    entries = TimetableEntry.objects.filter(teacher=teacher, is_active=True).select_related(
        "academic_year", "section", "section__grade", "subject", "time_slot"
    )
    day = request.GET.get("day", "")
    section_id = request.GET.get("section", "")
    subject_id = request.GET.get("subject", "")
    if day:
        entries = entries.filter(day=day)
    if section_id:
        entries = entries.filter(section_id=section_id)
    if subject_id:
        entries = entries.filter(subject_id=subject_id)

    available = TimetableEntry.objects.filter(teacher=teacher, is_active=True)
    sections = Section.objects.filter(timetable_entries__in=available).select_related("grade").distinct().order_by("grade__order", "name")
    subjects = Subject.objects.filter(timetableentry__in=available).select_related("grade").distinct().order_by("grade__order", "name")
    return render(request, "teachers/portal_timetable.html", {
        "teacher": teacher,
        "entries": entries,
        "sections": sections,
        "subjects": subjects,
        "days": TimetableEntry.DAYS,
        "filters": {"day": day, "section": section_id, "subject": subject_id},
    })


class AttendanceEntryForm(forms.Form):
    student_id = forms.IntegerField(widget=forms.HiddenInput)
    status = forms.ChoiceField(choices=Attendance.STATUS, widget=forms.Select(attrs={"class": "form-select"}))


@teacher_required
def portal_attendance(request, assignment_pk):
    """Compatibility route; attendance is allowed only to the homeroom teacher."""
    teacher = request.user.teacher_profile
    assignment = get_object_or_404(
        teacher.assignments.select_related("section", "section__grade", "subject", "academic_year"),
        pk=assignment_pk,
        is_active=True,
    )
    if assignment.section.homeroom_teacher_id != teacher.pk:
        messages.error(request, "تسجيل الغياب متاح لمربي الشعبة فقط.")
        return redirect("teachers:portal_dashboard")
    return redirect("teachers:portal_attendance_section", section_pk=assignment.section_id)


@teacher_required
def portal_attendance_section(request, section_pk):
    teacher = request.user.teacher_profile
    section = get_object_or_404(
        teacher.homeroom_sections.select_related("academic_year", "grade"),
        pk=section_pk,
        is_active=True,
    )
    date = request.POST.get("date") or request.GET.get("date") or timezone.localdate().isoformat()
    students = [
        enrollment.student
        for enrollment in Enrollment.objects.filter(
            section=section, academic_year=section.academic_year, status="active"
        ).select_related("student")
    ]
    FormSet = formset_factory(AttendanceEntryForm, extra=0)
    initial = []
    for student in students:
        record = Attendance.objects.filter(student=student, date=date).first()
        initial.append({
            "student_id": student.id,
            "status": record.status if record else "present",
        })
    formset = FormSet(request.POST or None, initial=initial)
    if request.method == "POST" and formset.is_valid():
        allowed = {student.id for student in students}
        saved = locked = 0
        for row in formset.cleaned_data:
            student_id = row.get("student_id")
            if student_id not in allowed:
                continue
            existing = Attendance.objects.filter(student_id=student_id, date=date).first()
            if existing and existing.is_locked:
                locked += 1
                continue
            status = row["status"]
            record, _ = Attendance.objects.update_or_create(
                student_id=student_id,
                date=date,
                defaults={
                    "academic_year": section.academic_year,
                    "grade": section.grade,
                    "section": section,
                    "status": status,
                    "notes": "",
                    "excuse_reason": "",
                    "departure_time": existing.departure_time if existing and status == "departed" else None,
                    "recorded_by": existing.recorded_by if existing else request.user,
                    "updated_by": request.user,
                },
            )
            notify_parent_for_attendance(record)
            saved += 1
        messages.success(request, f"تم حفظ حضور {saved} طالب.")
        if locked:
            messages.warning(request, f"تم تجاوز {locked} سجلًا مقفلًا.")
        return redirect(f"{request.path}?date={date}")
    rows = list(zip(students, formset.forms))
    return render(request, "teachers/portal_attendance.html", {
        "section": section,
        "assignment": None,
        "date": date,
        "rows": rows,
        "formset": formset,
    })


@teacher_required
def portal_students(request, assignment_pk):
    teacher = request.user.teacher_profile
    assignment = get_object_or_404(
        teacher.assignments.select_related("academic_year", "section", "section__grade", "subject"),
        pk=assignment_pk,
        is_active=True,
    )
    enrollments = Enrollment.objects.filter(
        academic_year=assignment.academic_year,
        section=assignment.section,
        status="active",
    ).select_related("student").order_by("student__full_name")
    return render(request, "teachers/portal_students.html", {"assignment": assignment, "enrollments": enrollments})


@teacher_required
def portal_homework(request, assignment_pk):
    teacher = request.user.teacher_profile
    assignment = get_object_or_404(
        teacher.assignments.select_related("academic_year", "section", "section__grade", "subject"),
        pk=assignment_pk,
        is_active=True,
    )
    form = HomeworkForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.assignment = assignment
        item.created_by = request.user
        item.save()
        enrollments = Enrollment.objects.filter(
            academic_year=assignment.academic_year,
            section=assignment.section,
            status="active",
        ).select_related("student")
        for enrollment in enrollments:
            notify_guardian_for_student(
                enrollment.student,
                "واجب جديد",
                f"تم نشر واجب {item.title} للطالب {enrollment.student.full_name}، والتسليم بتاريخ {item.due_date}.",
                event_key=f"homework:{item.pk}:student:{enrollment.student_id}",
                link="/parent/homework/",
            )
        messages.success(request, "تم نشر الواجب لطلاب الشعبة.")
        return redirect("teachers:portal_homework", assignment_pk=assignment.pk)
    items = assignment.homework_items.all()
    return render(request, "teachers/portal_homework.html", {"assignment": assignment, "form": form, "items": items})


@teacher_required
def portal_homework_update(request, pk):
    teacher = request.user.teacher_profile
    item = get_object_or_404(
        Homework.objects.select_related("assignment", "assignment__subject", "assignment__section"),
        pk=pk,
        assignment__teacher=teacher,
    )
    form = HomeworkForm(request.POST or None, request.FILES or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم تحديث الواجب.")
        return redirect("teachers:portal_homework", assignment_pk=item.assignment_id)
    return render(request, "teachers/portal_homework_form.html", {"item": item, "form": form})


@teacher_required
@require_POST
def portal_homework_delete(request, pk):
    teacher = request.user.teacher_profile
    item = get_object_or_404(Homework, pk=pk, assignment__teacher=teacher)
    assignment_id = item.assignment_id
    item.delete()
    messages.success(request, "تم حذف الواجب.")
    return redirect("teachers:portal_homework", assignment_pk=assignment_id)


@teacher_required
def portal_marks(request, assignment_pk):
    """Compatibility entry point to the single canonical marks screen."""
    teacher = request.user.teacher_profile
    assignment = get_object_or_404(
        teacher.assignments.select_related(
            "section", "section__grade", "subject", "academic_year"
        ),
        pk=assignment_pk,
        is_active=True,
    )
    exams = Exam.objects.filter(
        subject=assignment.subject,
        grade=assignment.section.grade,
        academic_year=assignment.academic_year,
        is_active=True,
    ).order_by("semester__code", "exam_type")
    exam_id = request.POST.get("exam") or request.GET.get("exam")
    exam = exams.filter(pk=exam_id).first() if exam_id else exams.first()
    if exam is None:
        messages.info(request, "لا توجد امتحانات متاحة لهذا التكليف حتى الآن.")
        return redirect("teachers:portal_dashboard")
    target = reverse("exams:exam_marks_bulk", args=[exam.pk])
    return redirect(f"{target}?assignment={assignment.pk}")
