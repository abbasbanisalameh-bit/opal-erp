from django.contrib import messages
from django.db import transaction
from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Prefetch, Q, Value
from decimal import Decimal
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import HomeworkForm, TeacherAccountCreateForm, TeacherAssignmentForm, TeacherForm
from .models import Homework, Teacher, TeacherAssignment, TeacherPerformanceSnapshot
from academics.models import Section, Subject
from .account_services import create_teacher_account, reset_teacher_password
from .tpi import (
    management_tpi_context,
    management_tpi_snapshot_context,
    teacher_tpi_snapshot_context,
)
from .workload import annual_subject_plan_map, teacher_workload_summary
from enterprise_ops.permissions import management_required
from enterprise_ops.services import audit
from parent_portal.notification_services import notify_guardian_for_student
from timetable.live_services import teacher_live_status
from core.request_scope import request_school
from core.secondary_effects import run_secondary_effect
from attendance_v2.services import notify_parent_for_attendance


@management_required
def dashboard(request):
    school = request_school(request)
    if request.method == "POST" and request.POST.get("action") == "refresh_tpi":
        if school is None:
            messages.error(request, "لا توجد مدرسة نشطة لحساب مؤشر TPI.")
        else:
            management_tpi_context(school=school)
            messages.success(request, "تم تحديث لقطات مؤشر TPI للشهر الحالي.")
        return redirect("teachers:dashboard")

    teachers = Teacher.objects.filter(school=school).select_related("school", "branch").annotate(
        assignments_count=Count(
            "assignments",
            filter=Q(assignments__is_active=True, assignments__academic_year__is_current=True),
            distinct=True,
        )
    )
    tpi = management_tpi_snapshot_context(school=school)
    context = {
        "teachers_count": teachers.count(),
        "active_count": teachers.filter(is_active=True).count(),
        "assignments_count": TeacherAssignment.objects.filter(
            teacher__school=school,
            is_active=True,
            academic_year__is_current=True,
        ).count(),
        "unassigned_count": teachers.filter(assignments_count=0).count(),
        "recent_teachers": teachers.order_by("-created_at")[:8],
        "tpi_period": tpi["period"],
        "tpi_top_teachers": tpi["top_teachers"],
    }
    return render(request, "teachers/dashboard.html", context)


@management_required
def teacher_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    school = request_school(request)
    current_assignments = TeacherAssignment.objects.filter(
        teacher__school=school,
        is_active=True,
        academic_year__is_current=True,
    ).select_related("academic_year", "section", "section__grade", "subject")
    teachers = Teacher.objects.filter(school=school).select_related("school", "branch", "user").prefetch_related(
        Prefetch("assignments", queryset=current_assignments, to_attr="current_assignments")
    ).annotate(
        assignments_count=Count(
            "assignments",
            filter=Q(assignments__is_active=True, assignments__academic_year__is_current=True),
            distinct=True,
        )
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
    teacher_rows = list(teachers)
    # The list is a read-only operational screen. Recalculating the complete
    # school TPI here previously executed many queries and writes every time
    # “عرض الجميع” was opened. Read the already-calculated monthly snapshots
    # in one query instead; the canonical TPI engine remains the only writer.
    tpi_period = timezone.localdate().replace(day=1)
    snapshots = {
        row.teacher_id: row
        for row in TeacherPerformanceSnapshot.objects.filter(
            teacher_id__in=[item.pk for item in teacher_rows],
            period=tpi_period,
        )
    }
    for teacher in teacher_rows:
        teacher.tpi_snapshot = snapshots.get(teacher.pk)
    return render(request, "teachers/teacher_list.html", {"teachers": teacher_rows, "query": query, "status": status})


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
    teacher = get_object_or_404(Teacher.objects.select_related("school", "branch", "user"), pk=pk)
    assignments = list(teacher.assignments.select_related("academic_year", "section", "section__grade", "subject"))
    plans_by_year = {}
    for assignment in assignments:
        assignment.plan_periods = assignment.subject.weekly_periods
    timetable_entries = teacher.timetable_entries.select_related(
        "academic_year", "section", "section__grade", "subject", "time_slot"
    ).filter(is_active=True)
    issued_documents = list(teacher.issued_documents.select_related("template").all())
    latest_termination_document = next(
        (
            document
            for document in issued_documents
            if document.template_id and document.template.code == "teacher-termination"
        ),
        None,
    )
    from timetable.workflow import build_horizontal_schedule_matrix
    timetable_matrix = build_horizontal_schedule_matrix(timetable_entries, school=teacher.school)
    return render(request, "teachers/teacher_detail.html", {
        "teacher": teacher, "assignments": assignments, "timetable_entries": timetable_entries,
        "timetable_matrix": timetable_matrix,
        "teacher_documents": teacher.documents.all(),
        "issued_documents": issued_documents,
        "latest_termination_document": latest_termination_document,
        "workload": teacher_workload_summary(teacher),
    })


@management_required
@require_POST
def teacher_toggle(request, pk):
    teacher = get_object_or_404(Teacher.objects.select_related("user"), pk=pk)
    if teacher.is_active:
        messages.warning(
            request,
            "إيقاف المعلم النشط يتم فقط من إجراء إنهاء الخدمة حتى تُحفظ الأسباب ويصدر الكتاب الرسمي.",
        )
        return redirect("teachers:teacher_terminate", pk=teacher.pk)

    from .payroll_services import reactivate_teacher
    from django.core.exceptions import ValidationError

    try:
        teacher, summary = reactivate_teacher(teacher=teacher)
    except ValidationError as exc:
        messages.error(request, getattr(exc, "messages", [str(exc)])[0])
    else:
        audit(
            request,
            "update",
            "teachers.Teacher",
            teacher.pk,
            f"إعادة تفعيل المعلم دون إعادة التكليفات السابقة: {summary}",
        )
        messages.success(
            request,
            "تم تفعيل المعلم وحساب الدخول. لم تُعد التكليفات أو حصص الجدول القديمة تلقائيًا؛ راجع التكليفات الحالية قبل إسناد العمل.",
        )
    return redirect("teachers:teacher_detail", pk=teacher.pk)


@management_required
def assignment_create(request, teacher_pk):
    teacher = get_object_or_404(Teacher, pk=teacher_pk)
    if not teacher.is_active:
        messages.error(request, "لا يمكن إضافة تكليف لمعلم غير نشط. أعد تفعيل المعلم أولًا.")
        return redirect("teachers:teacher_detail", pk=teacher.pk)
    form = TeacherAssignmentForm(request.POST or None, teacher=teacher)
    if form.is_valid():
        with transaction.atomic():
            assignment = form.save(commit=False)
            assignment.teacher = teacher
            assignment.save()
            form.save_teacher_workload()
        messages.success(request, "تم حفظ التكليف التدريسي وتحديث نصاب المعلم.")
        return redirect("teachers:teacher_detail", pk=teacher.pk)
    return render(request, "teachers/assignment_form.html", {
        "form": form, "teacher": teacher, "title": "إضافة تكليف تدريسي",
        "workload": teacher_workload_summary(teacher),
    })


@management_required
def assignment_update(request, pk):
    assignment = get_object_or_404(TeacherAssignment.objects.select_related("teacher"), pk=pk)
    if assignment.academic_year.is_closed:
        messages.error(request, "العام الدراسي مغلق ولا يمكن تعديل تكليفاته التاريخية.")
        return redirect("teachers:teacher_detail", pk=assignment.teacher_id)
    form = TeacherAssignmentForm(request.POST or None, instance=assignment, teacher=assignment.teacher)
    if form.is_valid():
        with transaction.atomic():
            form.save()
            form.save_teacher_workload()
        messages.success(request, "تم تحديث التكليف التدريسي ونصاب المعلم.")
        return redirect("teachers:teacher_detail", pk=assignment.teacher_id)
    return render(request, "teachers/assignment_form.html", {
        "form": form, "teacher": assignment.teacher, "title": "تعديل التكليف التدريسي",
        "workload": teacher_workload_summary(assignment.teacher, assignment.academic_year),
    })


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
    if not teacher.is_active:
        messages.error(request, "لا يمكن إنشاء حساب دخول لمعلم غير نشط. أعد تفعيل المعلم أولًا.")
        return redirect("teachers:teacher_detail", pk=teacher.pk)
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
from attendance_v2.models import Attendance, AttendanceRegister
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
        "section__grade", "subject", "time_slot"
    )
    homeroom_sections = teacher.homeroom_sections.filter(is_active=True).select_related(
        "academic_year", "grade"
    )
    latest_homework = Homework.objects.filter(
        assignment__teacher=teacher, is_active=True
    ).select_related("assignment__subject", "assignment__section")[:10]
    from exams.models import Exam
    open_exams = Exam.objects.filter(
        teacher_assignment__teacher=teacher,
        teacher_assignment__is_active=True,
        status__in=["open", "draft"],
        is_active=True,
    ).select_related(
        "academic_year", "semester", "section", "subject", "teacher_assignment"
    ).order_by("exam_date", "subject__name", "exam_type")
    submitted_exams = Exam.objects.filter(
        teacher_assignment__teacher=teacher,
        status="submitted",
        is_active=True,
    ).select_related("section", "subject").order_by("-submitted_at")[:10]
    tpi = teacher_tpi_snapshot_context(teacher)
    snapshot = tpi["snapshot"]
    from timetable.workflow import build_horizontal_schedule_matrix
    timetable_matrix = build_horizontal_schedule_matrix(timetable, school=teacher.school)
    return render(request, "teachers/portal_dashboard.html", {
        "teacher": teacher,
        "assignments": assignments,
        "timetable": timetable,
        "timetable_matrix": timetable_matrix,
        "homeroom_sections": homeroom_sections,
        "latest_homework": latest_homework,
        "open_exams": open_exams,
        "submitted_exams": submitted_exams,
        "live_status": teacher_live_status(teacher),
        "tpi": tpi,
        "tpi_components": snapshot.components.get("components", []) if snapshot else [],
        "workload": teacher_workload_summary(teacher),
    })


@teacher_required
def portal_workspace(request):
    """Small, scoped launchpad for teacher work.

    The portal deliberately does not fetch a whole school worth of students,
    marks or homework.  The teacher first chooses the grade, subject and
    section from their own active assignments, then opens exactly one action.
    """
    teacher = request.user.teacher_profile
    assignments = list(teacher.assignments.filter(is_active=True).select_related(
        "academic_year", "section", "section__grade", "subject"
    ).order_by("section__grade__order", "subject__name", "section__name"))
    mode = request.GET.get("mode", "subjects")
    if mode not in {"subjects", "students", "marks", "homework"}:
        mode = "subjects"
    grade_id = request.GET.get("grade", "")
    subject_id = request.GET.get("subject", "")
    section_id = request.GET.get("section", "")
    assignment_id = request.GET.get("assignment", "")

    grades = []
    seen_grades = set()
    for assignment in assignments:
        if assignment.section.grade_id not in seen_grades:
            grades.append(assignment.section.grade)
            seen_grades.add(assignment.section.grade_id)
    grade_assignments = [a for a in assignments if not grade_id or str(a.section.grade_id) == grade_id]
    subjects = []
    seen_subjects = set()
    for assignment in grade_assignments:
        if assignment.subject_id not in seen_subjects:
            subjects.append(assignment.subject)
            seen_subjects.add(assignment.subject_id)
    subject_assignments = [a for a in grade_assignments if not subject_id or str(a.subject_id) == subject_id]
    sections = []
    seen_sections = set()
    for assignment in subject_assignments:
        if assignment.section_id not in seen_sections:
            sections.append(assignment.section)
            seen_sections.add(assignment.section_id)
    available_assignments = [a for a in subject_assignments if not section_id or str(a.section_id) == section_id]
    selected_assignment = next((a for a in available_assignments if str(a.pk) == assignment_id), None)
    workspace_enrollments = Enrollment.objects.none()
    if mode == "students" and section_id:
        section_assignment = next((a for a in assignments if str(a.section_id) == section_id), None)
        if section_assignment:
            workspace_enrollments = Enrollment.objects.filter(
                academic_year=section_assignment.academic_year,
                section_id=section_id,
                status="active",
            ).select_related("student").order_by("student__full_name")
    return render(request, "teachers/portal_workspace.html", {
        "teacher": teacher,
        "mode": mode,
        "grades": grades,
        "subjects": subjects,
        "sections": sections,
        "assignments": available_assignments,
        "selected_assignment": selected_assignment,
        "workspace_enrollments": workspace_enrollments,
        "filters": {
            "grade": grade_id, "subject": subject_id,
            "section": section_id, "assignment": assignment_id,
        },
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
    from timetable.workflow import build_horizontal_schedule_matrix
    schedule_matrix = build_horizontal_schedule_matrix(
        entries,
        selected_day=day,
        school=teacher.school,
        show_free=True,
        reference_entries=available.select_related("section__grade", "subject", "time_slot"),
    )
    return render(request, "teachers/portal_timetable.html", {
        "teacher": teacher,
        "entries": entries,
        "schedule_matrix": schedule_matrix,
        "sections": sections,
        "subjects": subjects,
        "days": TimetableEntry.DAYS,
        "filters": {"day": day, "section": section_id, "subject": subject_id},
    })


class AttendanceEntryForm(forms.Form):
    student_id = forms.IntegerField(widget=forms.HiddenInput)
    status = forms.ChoiceField(required=False, choices=[("", "حاضر تلقائيًا")] + Attendance.STATUS, widget=forms.Select(attrs={"class": "form-select"}))


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
    selected_date = request.POST.get("date") or request.GET.get("date") or timezone.localdate().isoformat()
    students = [
        enrollment.student
        for enrollment in Enrollment.objects.filter(
            section=section, academic_year=section.academic_year, status="active"
        ).select_related("student")
    ]
    # Opening the page is not a business action.  The official daily register
    # is created only after the teacher submits attendance, so TPI never treats
    # a page view as student-attendance work.
    register = AttendanceRegister.objects.filter(
        section=section,
        date=selected_date,
    ).first()
    FormSet = formset_factory(AttendanceEntryForm, extra=0)
    existing_by_student = {
        item.student_id: item
        for item in Attendance.objects.filter(section=section, date=selected_date)
    }
    initial = [
        {
            "student_id": student.id,
            "status": existing_by_student.get(student.id).status if student.id in existing_by_student else "",
        }
        for student in students
    ]
    formset = FormSet(request.POST or None, initial=initial)
    can_edit = register is None or (
        not register.is_teacher_locked and not register.is_admin_closed
    )
    if request.method == "POST":
        if not can_edit:
            messages.error(request, "سجل هذا اليوم مغلق ولا يمكن للمعلم تعديله.")
            return redirect(f"{request.path}?date={selected_date}")
        if formset.is_valid():
            allowed = {student.id for student in students}
            saved = removed = 0
            with transaction.atomic():
                register, _ = AttendanceRegister.objects.get_or_create(
                    section=section,
                    date=selected_date,
                    defaults={
                        "academic_year": section.academic_year,
                        "grade": section.grade,
                        "created_by": request.user,
                    },
                )
                for row in formset.cleaned_data:
                    student_id = row.get("student_id")
                    if student_id not in allowed:
                        continue
                    status = row.get("status")
                    existing = Attendance.objects.select_for_update().filter(
                        student_id=student_id, date=selected_date
                    ).first()
                    if not status:
                        if existing:
                            existing.delete()
                            removed += 1
                        continue
                    record, _ = Attendance.objects.update_or_create(
                        student_id=student_id,
                        date=selected_date,
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
                    transaction.on_commit(
                        lambda item=record: run_secondary_effect(
                            notify_parent_for_attendance,
                            item,
                            label="attendance parent notification",
                        )
                    )
                    saved += 1
                register.submitted_by = request.user
                register.submitted_at = timezone.now()
                register.save(update_fields=["submitted_by", "submitted_at", "updated_at"])
            messages.success(request, f"تم حفظ {saved} حالة غياب أو مغادرة. الحاضرون لا يُنشأ لهم سجل.")
            return redirect(f"{request.path}?date={selected_date}")
    rows = list(zip(students, formset.forms))
    return render(request, "teachers/portal_attendance.html", {
        "section": section,
        "assignment": None,
        "date": selected_date,
        "rows": rows,
        "formset": formset,
        "register": register,
        "can_edit": can_edit,
    })


@teacher_required
def portal_students(request, assignment_pk):
    """Compatibility redirect to the scoped teacher workspace students mode."""
    teacher = request.user.teacher_profile
    assignment = get_object_or_404(
        teacher.assignments.select_related("academic_year", "section", "section__grade", "subject"),
        pk=assignment_pk,
        is_active=True,
    )
    target = reverse("teachers:portal_workspace")
    return redirect(
        f"{target}?mode=students&grade={assignment.section.grade_id}&subject={assignment.subject_id}"
        f"&section={assignment.section_id}&assignment={assignment.pk}"
    )


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
                link=f"{reverse('parent_portal:homework')}?student={enrollment.student_id}&subject={assignment.subject_id}",
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
