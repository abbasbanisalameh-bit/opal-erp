from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import Section
from core.models import AcademicYear
from teachers.models import Teacher

from enterprise_ops.services import audit
from .forms import TimeSlotForm, TimetableEntryForm
from .models import TimeSlot, TimetableEntry


@staff_member_required
def dashboard(request):
    entries = TimetableEntry.objects.select_related(
        "academic_year", "section__grade", "subject", "teacher", "time_slot"
    )
    year_id = request.GET.get("academic_year", "")
    section_id = request.GET.get("section", "")
    teacher_id = request.GET.get("teacher", "")
    day = request.GET.get("day", "")
    q = request.GET.get("q", "").strip()
    if year_id:
        entries = entries.filter(academic_year_id=year_id)
    if section_id:
        entries = entries.filter(section_id=section_id)
    if teacher_id:
        entries = entries.filter(teacher_id=teacher_id)
    if day:
        entries = entries.filter(day=day)
    if q:
        entries = entries.filter(
            Q(section__grade__name__icontains=q)
            | Q(section__name__icontains=q)
            | Q(subject__name__icontains=q)
            | Q(teacher__full_name__icontains=q)
            | Q(room__icontains=q)
        )
    return render(
        request,
        "timetable/dashboard.html",
        {
            "entries": entries,
            "academic_years": AcademicYear.objects.order_by("-start_date"),
            "sections": Section.objects.select_related("grade").filter(is_active=True),
            "teachers": Teacher.objects.filter(is_active=True),
            "days": TimetableEntry.DAYS,
            "filters": {
                "academic_year": year_id,
                "section": section_id,
                "teacher": teacher_id,
                "day": day,
                "q": q,
            },
        },
    )


@staff_member_required
def entry_create(request):
    form = TimetableEntryForm(request.POST or None)
    if form.is_valid():
        entry = form.save()
        audit(request, "create", "timetable.TimetableEntry", entry.pk, f"إنشاء حصة: {entry}")
        messages.success(request, "تمت إضافة الحصة إلى الجدول.")
        return redirect("timetable:dashboard")
    return render(request, "timetable/form.html", {"form": form, "title": "إضافة حصة"})


@staff_member_required
def entry_update(request, pk):
    entry = get_object_or_404(TimetableEntry, pk=pk)
    form = TimetableEntryForm(request.POST or None, instance=entry)
    if form.is_valid():
        entry = form.save()
        audit(request, "update", "timetable.TimetableEntry", entry.pk, f"تعديل حصة: {entry}")
        messages.success(request, "تم تحديث الحصة.")
        return redirect("timetable:dashboard")
    return render(request, "timetable/form.html", {"form": form, "title": "تعديل حصة", "entry": entry})


@staff_member_required
def entry_delete(request, pk):
    entry = get_object_or_404(TimetableEntry, pk=pk)
    if request.method == "POST":
        description = str(entry)
        entry.delete()
        audit(request, "delete", "timetable.TimetableEntry", pk, f"حذف حصة: {description}")
        messages.success(request, "تم حذف الحصة.")
    return redirect("timetable:dashboard")


@staff_member_required
def slot_list(request):
    return render(request, "timetable/slot_list.html", {"slots": TimeSlot.objects.all()})


@staff_member_required
def slot_create(request):
    form = TimeSlotForm(request.POST or None)
    if form.is_valid():
        slot = form.save()
        audit(request, "create", "timetable.TimeSlot", slot.pk, f"إنشاء وقت حصة: {slot}")
        messages.success(request, "تمت إضافة وقت الحصة.")
        return redirect("timetable:slot_list")
    return render(request, "timetable/form.html", {"form": form, "title": "إضافة وقت حصة"})


@staff_member_required
def slot_update(request, pk):
    slot = get_object_or_404(TimeSlot, pk=pk)
    form = TimeSlotForm(request.POST or None, instance=slot)
    if form.is_valid():
        form.save()
        audit(request, "update", "timetable.TimeSlot", slot.pk, f"تعديل وقت حصة: {slot}")
        messages.success(request, "تم تحديث وقت الحصة.")
        return redirect("timetable:slot_list")
    return render(request, "timetable/form.html", {"form": form, "title": "تعديل وقت حصة"})


@staff_member_required
def slot_delete(request, pk):
    slot = get_object_or_404(TimeSlot, pk=pk)
    if request.method == "POST":
        if slot.entries.exists():
            messages.error(request, "لا يمكن حذف وقت مرتبط بحصص. أوقف تفعيله بدلًا من ذلك.")
        else:
            slot.delete()
            audit(request, "delete", "timetable.TimeSlot", pk, "حذف وقت حصة")
            messages.success(request, "تم حذف وقت الحصة.")
    return redirect("timetable:slot_list")


def _print_context(entries, title):
    days = []
    for code, label in TimetableEntry.DAYS:
        days.append((label, entries.filter(day=code)))
    return {"title": title, "days": days}


@staff_member_required
def section_print(request, section_id):
    section = get_object_or_404(Section.objects.select_related("grade"), pk=section_id)
    entries = TimetableEntry.objects.filter(section=section, is_active=True).select_related(
        "subject", "teacher", "time_slot"
    )
    audit(request, "print", "timetable.SectionSchedule", section.pk, f"طباعة جدول {section}")
    return render(request, "timetable/print.html", _print_context(entries, f"جدول {section}"))


@staff_member_required
def teacher_print(request, teacher_id):
    teacher = get_object_or_404(Teacher, pk=teacher_id)
    entries = TimetableEntry.objects.filter(teacher=teacher, is_active=True).select_related(
        "section__grade", "subject", "time_slot"
    )
    audit(request, "print", "timetable.TeacherSchedule", teacher.pk, f"طباعة جدول {teacher}")
    return render(request, "timetable/print.html", _print_context(entries, f"جدول المعلم {teacher}"))
