from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import TeacherAssignmentForm, TeacherForm
from .models import Teacher, TeacherAssignment


@staff_member_required
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


@staff_member_required
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


@staff_member_required
def teacher_create(request):
    form = TeacherForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        teacher = form.save()
        messages.success(request, "تمت إضافة المعلم بنجاح.")
        return redirect("teachers:teacher_detail", pk=teacher.pk)
    return render(request, "teachers/teacher_form.html", {"form": form, "title": "إضافة معلم"})


@staff_member_required
def teacher_update(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    form = TeacherForm(request.POST or None, request.FILES or None, instance=teacher)
    if form.is_valid():
        form.save()
        messages.success(request, "تم تحديث بيانات المعلم.")
        return redirect("teachers:teacher_detail", pk=teacher.pk)
    return render(request, "teachers/teacher_form.html", {"form": form, "title": "تعديل بيانات المعلم", "teacher": teacher})


@staff_member_required
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
    })


@staff_member_required
def teacher_toggle(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    if request.method == "POST":
        teacher.is_active = not teacher.is_active
        teacher.save(update_fields=["is_active"])
        messages.success(request, "تم تحديث حالة المعلم.")
    return redirect("teachers:teacher_detail", pk=teacher.pk)


@staff_member_required
def assignment_create(request, teacher_pk):
    teacher = get_object_or_404(Teacher, pk=teacher_pk)
    form = TeacherAssignmentForm(request.POST or None)
    if form.is_valid():
        assignment = form.save(commit=False)
        assignment.teacher = teacher
        assignment.save()
        messages.success(request, "تم حفظ التكليف التدريسي.")
        return redirect("teachers:teacher_detail", pk=teacher.pk)
    return render(request, "teachers/assignment_form.html", {"form": form, "teacher": teacher, "title": "إضافة تكليف تدريسي"})


@staff_member_required
def assignment_update(request, pk):
    assignment = get_object_or_404(TeacherAssignment.objects.select_related("teacher"), pk=pk)
    form = TeacherAssignmentForm(request.POST or None, instance=assignment)
    if form.is_valid():
        form.save()
        messages.success(request, "تم تحديث التكليف التدريسي.")
        return redirect("teachers:teacher_detail", pk=assignment.teacher_id)
    return render(request, "teachers/assignment_form.html", {"form": form, "teacher": assignment.teacher, "title": "تعديل التكليف التدريسي"})


@staff_member_required
def assignment_delete(request, pk):
    assignment = get_object_or_404(TeacherAssignment, pk=pk)
    teacher_id = assignment.teacher_id
    if request.method == "POST":
        assignment.delete()
        messages.success(request, "تم حذف التكليف التدريسي.")
    return redirect("teachers:teacher_detail", pk=teacher_id)

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
            academic_year__name=assignment.academic_year.name,
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
        allowed={s.id for s in students}
        for row in formset.cleaned_data:
            sid=row.get("student_id")
            if sid in allowed:
                Attendance.objects.update_or_create(student_id=sid,date=date,defaults={"status":row["status"],"notes":row.get("notes","")})
        messages.success(request,"تم حفظ الحضور بنجاح.")
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
    # TeacherAssignment uses academics.AcademicYear while Exam uses
    # core.AcademicYear. Match by year name to avoid cross-model FK errors.
    exams=Exam.objects.filter(
        subject=assignment.subject,
        grade=assignment.section.grade,
        academic_year__name=assignment.academic_year.name,
        is_active=True,
    )
    exam_id=request.POST.get("exam") or request.GET.get("exam")
    exam=get_object_or_404(exams,pk=exam_id) if exam_id else exams.first()
    students=[
        e.student
        for e in Enrollment.objects.filter(
            section=assignment.section,
            academic_year__name=assignment.academic_year.name,
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
        allowed={s.id for s in students}
        for row in formset.cleaned_data:
            sid=row.get("student_id")
            if sid in allowed and row["mark"] <= exam.max_mark:
                StudentMark.objects.update_or_create(student_id=sid,exam=exam,defaults={"mark":row["mark"],"notes":row.get("notes","")})
        messages.success(request,"تم حفظ العلامات بنجاح.")
        return redirect(f"{request.path}?exam={exam.id}")
    return render(request,"teachers/portal_marks.html",{"assignment":assignment,"exams":exams,"exam":exam,"rows":list(zip(students,formset.forms)),"formset":formset})
