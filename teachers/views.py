from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import TeacherAccountCreateForm, TeacherAssignmentForm, TeacherForm
from .models import Teacher, TeacherAssignment
from .account_services import create_teacher_account, reset_teacher_password
from enterprise_ops.permissions import management_required


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
from exams.models import Exam, StudentMark
from timetable.models import TimetableEntry
from .permissions import teacher_required


@teacher_required
def portal_dashboard(request):
    teacher = request.user.teacher_profile
    assignments = teacher.assignments.filter(is_active=True).select_related("academic_year", "section", "section__grade", "subject")
    timetable = TimetableEntry.objects.filter(teacher=teacher, is_active=True).select_related("section", "subject", "time_slot")
    return render(request, "teachers/portal_dashboard.html", {"teacher": teacher, "assignments": assignments, "timetable": timetable})


class AttendanceEntryForm(forms.Form):
    student_id = forms.IntegerField(widget=forms.HiddenInput)
    status = forms.ChoiceField(choices=Attendance.STATUS, widget=forms.Select(attrs={"class": "form-select"}))
    notes = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))


@teacher_required
def portal_attendance(request, assignment_pk):
    teacher = request.user.teacher_profile
    assignment = get_object_or_404(teacher.assignments.select_related("section", "subject"), pk=assignment_pk, is_active=True)
    date = request.POST.get("date") or request.GET.get("date") or timezone.localdate().isoformat()
    students = [
        e.student
        for e in Enrollment.objects.filter(
            section=assignment.section,
            academic_year=assignment.academic_year,
            status="active",
        ).select_related("student")
    ]
    FormSet = formset_factory(AttendanceEntryForm, extra=0)
    initial=[]
    for st in students:
        rec=Attendance.objects.filter(student=st,date=date).first()
        initial.append({"student_id":st.id,"status":rec.status if rec else "present","notes":rec.notes if rec else ""})
    formset=FormSet(request.POST or None, initial=initial)
    if request.method == "POST" and formset.is_valid():
        allowed={student.id for student in students}
        saved = locked = 0
        for row in formset.cleaned_data:
            sid=row.get("student_id")
            if sid not in allowed:
                continue
            existing = Attendance.objects.filter(student_id=sid, date=date).first()
            if existing and existing.is_locked:
                locked += 1
                continue
            Attendance.objects.update_or_create(
                student_id=sid, date=date,
                defaults={
                    "academic_year": assignment.academic_year,
                    "grade": assignment.section.grade,
                    "section": assignment.section,
                    "status": row["status"],
                    "notes": row.get("notes", ""),
                    "recorded_by": existing.recorded_by if existing else request.user,
                    "updated_by": request.user,
                },
            )
            saved += 1
        messages.success(request, f"تم حفظ حضور {saved} طالب.")
        if locked:
            messages.warning(request, f"تم تجاوز {locked} سجلًا مقفلًا.")
        return redirect(f"{request.path}?date={date}")
    rows=list(zip(students, formset.forms))
    return render(request,"teachers/portal_attendance.html",{"assignment":assignment,"date":date,"rows":rows,"formset":formset})


class MarkEntryForm(forms.Form):
    student_id=forms.IntegerField(widget=forms.HiddenInput)
    mark=forms.DecimalField(min_value=0, widget=forms.NumberInput(attrs={"class":"form-control","step":"0.01"}))
    notes=forms.CharField(required=False,widget=forms.TextInput(attrs={"class":"form-control"}))


@teacher_required
def portal_marks(request, assignment_pk):
    teacher=request.user.teacher_profile
    assignment=get_object_or_404(teacher.assignments.select_related("section","section__grade","subject","academic_year"),pk=assignment_pk,is_active=True)
    exams=Exam.objects.filter(
        subject=assignment.subject,
        grade=assignment.section.grade,
        academic_year=assignment.academic_year,
        is_active=True,
    )
    exam_id=request.POST.get("exam") or request.GET.get("exam")
    exam=get_object_or_404(exams,pk=exam_id) if exam_id else exams.first()
    students=[
        e.student
        for e in Enrollment.objects.filter(
            section=assignment.section,
            academic_year=assignment.academic_year,
            status="active",
        ).select_related("student")
    ]
    FormSet=formset_factory(MarkEntryForm,extra=0)
    initial=[]
    if exam:
        for st in students:
            rec=StudentMark.objects.filter(student=st,exam=exam).first()
            initial.append({"student_id":st.id,"mark":rec.mark if rec else 0,"notes":rec.notes if rec else ""})
    formset=FormSet(request.POST or None,initial=initial)
    if request.method=="POST" and exam and formset.is_valid():
        if not exam.can_edit_marks:
            messages.error(request, "الامتحان معتمد أو مقفل ولا يمكن تعديل علاماته.")
            return redirect(f"{request.path}?exam={exam.id}")
        allowed={student.id for student in students}
        saved = 0
        for row in formset.cleaned_data:
            sid=row.get("student_id")
            if sid in allowed and row["mark"] <= exam.max_mark:
                mark, created = StudentMark.objects.get_or_create(
                    student_id=sid, exam=exam,
                    defaults={"mark": row["mark"], "notes": row.get("notes", ""), "entered_by": request.user, "updated_by": request.user},
                )
                if not created:
                    mark.mark = row["mark"]
                    mark.notes = row.get("notes", "")
                    mark.updated_by = request.user
                    mark.full_clean()
                    mark.save()
                saved += 1
        messages.success(request, f"تم حفظ {saved} علامة بنجاح.")
        return redirect(f"{request.path}?exam={exam.id}")
    return render(request,"teachers/portal_marks.html",{"assignment":assignment,"exams":exams,"exam":exam,"rows":list(zip(students,formset.forms)),"formset":formset})
