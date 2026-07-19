from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import Grade, Section, Subject
from core.models import AcademicYear
from teachers.models import Teacher
from admissions.services import active_school, current_academic_year

from enterprise_ops.services import audit
from .forms import (
    CoverageAssignmentForm, SchoolDayEventForm, SchoolScheduleSettingsForm,
    TeacherAbsenceForm, TimeSlotForm, TimetableEntryForm,
)
from .live_services import DAY_CODES, management_live_status
from .models import ClassCoverage, SchoolDayEvent, SchoolScheduleSettings, TeacherAbsence, TimeSlot, TimetableEntry
from .services import build_smart_timetable


@staff_member_required
def dashboard(request):
    entries = TimetableEntry.objects.select_related(
        "academic_year", "section__grade", "subject", "teacher", "time_slot"
    )
    year_id = request.GET.get("academic_year", "")
    grade_id = request.GET.get("grade", "")
    section_id = request.GET.get("section", "")
    teacher_id = request.GET.get("teacher", "")
    subject_id = request.GET.get("subject", "")
    day = request.GET.get("day", "")
    q = request.GET.get("q", "").strip()
    if year_id:
        entries = entries.filter(academic_year_id=year_id)
    if grade_id:
        entries = entries.filter(section__grade_id=grade_id)
    if section_id:
        entries = entries.filter(section_id=section_id)
    if teacher_id:
        entries = entries.filter(teacher_id=teacher_id)
    if subject_id:
        entries = entries.filter(subject_id=subject_id)
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
            "grades": Grade.objects.order_by("order", "name"),
            "sections": Section.objects.select_related("grade").filter(is_active=True),
            "teachers": Teacher.objects.filter(is_active=True),
            "subjects": Subject.objects.filter(is_active=True).select_related("grade").order_by("grade__order", "name"),
            "days": TimetableEntry.DAYS,
            "filters": {
                "academic_year": year_id,
                "grade": grade_id,
                "section": section_id,
                "teacher": teacher_id,
                "subject": subject_id,
                "day": day,
                "q": q,
            },
            "live_status": management_live_status(active_school()),
            "coverage_needed": ClassCoverage.objects.filter(date=timezone.localdate(), status="needed").select_related("entry__section", "entry__subject", "entry__teacher", "entry__time_slot"),
        },
    )


@staff_member_required
def smart_builder(request):
    school = active_school()
    years = AcademicYear.objects.filter(school=school, is_closed=False).order_by("-is_current", "-start_date")
    year_id = request.POST.get("academic_year") or request.GET.get("academic_year")
    year = years.filter(pk=year_id).first() if year_id else years.first()
    result = None
    if year:
        apply = request.method == "POST" and request.POST.get("action") == "apply"
        replace = request.POST.get("replace_generated") == "1"
        result = build_smart_timetable(academic_year=year, apply=apply, replace_generated=replace)
        if apply:
            audit(request, "create", "timetable.SmartBuilder", year.pk, f"بناء الجدول الذكي: {len(result['created'])} حصة")
            if result["unresolved"]:
                messages.warning(request, f"تم إنشاء {len(result['created'])} حصة، وتعذر إسناد {len(result['unresolved'])} تكليفات لعدم توفر وقت خالٍ.")
            else:
                messages.success(request, f"تم إنشاء {len(result['created'])} حصة دون تعديل الحصص اليدوية.")
            return redirect(f"{request.path}?academic_year={year.pk}")
    return render(request, "timetable/smart_builder.html", {"years": years, "year": year, "result": result})


@staff_member_required
def schedule_settings(request):
    school = active_school()
    settings, _ = SchoolScheduleSettings.objects.get_or_create(school=school)
    settings_form = SchoolScheduleSettingsForm(prefix="settings", instance=settings)
    event_form = SchoolDayEventForm(prefix="event")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "settings":
            settings_form = SchoolScheduleSettingsForm(request.POST, prefix="settings", instance=settings)
            if settings_form.is_valid():
                item = settings_form.save(commit=False)
                item.updated_by = request.user
                item.save()
                messages.success(request, "تم حفظ أيام العطلة ومدة التنبيه.")
                return redirect("timetable:schedule_settings")
        elif action == "event":
            event_form = SchoolDayEventForm(request.POST, prefix="event")
            if event_form.is_valid():
                event = event_form.save(commit=False)
                event.school = school
                event.save()
                messages.success(request, "تمت إضافة الحدث إلى المؤقت المدرسي.")
                return redirect("timetable:schedule_settings")
    return render(request, "timetable/schedule_settings.html", {
        "settings_form": settings_form, "event_form": event_form,
        "events": SchoolDayEvent.objects.filter(school=school),
    })


@staff_member_required
@require_POST
def event_delete(request, pk):
    event = get_object_or_404(SchoolDayEvent, pk=pk)
    event.delete()
    messages.success(request, "تم حذف الحدث من المؤقت.")
    return redirect("timetable:schedule_settings")


@staff_member_required
def absence_center(request):
    school = active_school()
    form = TeacherAbsenceForm(request.POST or None)
    form.fields["teacher"].queryset = Teacher.objects.filter(school=school, is_active=True)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                absence = form.save(commit=False)
                absence.recorded_by = request.user
                absence.save()
                day = DAY_CODES[absence.date.weekday()]
                entries = TimetableEntry.objects.filter(
                    teacher=absence.teacher, day=day, academic_year__school=school,
                    academic_year__is_current=True, is_active=True,
                )
                for entry in entries:
                    ClassCoverage.objects.get_or_create(entry=entry, date=absence.date)
        except Exception as exc:
            form.add_error(None, "غياب هذا المعلم مسجل لهذا التاريخ مسبقًا." if "uniq" in str(exc).lower() else str(exc))
        else:
            audit(request, "create", "timetable.TeacherAbsence", absence.pk, f"تسجيل غياب {absence.teacher} وإنشاء إشغالات الحصص")
            messages.success(request, "تم تسجيل الغياب وإنشاء تنبيه إشغال لكل حصة للمعلم في ذلك اليوم.")
            return redirect("timetable:absence_center")
    coverages = ClassCoverage.objects.filter(date__gte=timezone.localdate()).select_related(
        "entry__teacher", "entry__section", "entry__subject", "entry__time_slot", "substitute_teacher"
    ).order_by("date", "entry__time_slot__order")
    return render(request, "timetable/absence_center.html", {"form": form, "coverages": coverages})


@staff_member_required
def coverage_assign(request, pk):
    coverage = get_object_or_404(ClassCoverage.objects.select_related("entry__academic_year__school", "entry__time_slot"), pk=pk)
    form = CoverageAssignmentForm(request.POST or None, instance=coverage)
    form.fields["substitute_teacher"].queryset = Teacher.objects.filter(school=coverage.entry.academic_year.school, is_active=True).exclude(pk=coverage.entry.teacher_id)
    if request.method == "POST" and form.is_valid():
        substitute = form.cleaned_data["substitute_teacher"]
        busy = TimetableEntry.objects.filter(
            teacher=substitute, academic_year=coverage.entry.academic_year, day=coverage.entry.day,
            time_slot=coverage.entry.time_slot, is_active=True,
        ).exists()
        absent = TeacherAbsence.objects.filter(teacher=substitute, date=coverage.date).exists()
        if busy or absent:
            form.add_error("substitute_teacher", "المعلم المختار مشغول بحصة أخرى أو مسجل غائبًا في هذا الوقت.")
        else:
            coverage = form.save(commit=False)
            coverage.status = "assigned"
            coverage.assigned_by = request.user
            coverage.save()
            messages.success(request, "تم تعيين المعلم البديل وإغلاق تنبيه الإشغال.")
            return redirect("timetable:absence_center")
    return render(request, "timetable/form.html", {"form": form, "title": "تعيين معلم بديل", "coverage": coverage})


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
    if entry.academic_year.is_closed:
        messages.error(request, "العام الدراسي مغلق ولا يمكن تعديل جدوله التاريخي.")
        return redirect("timetable:dashboard")
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
        if entry.academic_year.is_closed:
            messages.error(request, "العام الدراسي مغلق ولا يمكن حذف جدوله التاريخي.")
        else:
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
