from datetime import date

from django.contrib import messages
from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import Grade, Section, Subject
from core.models import AcademicYear
from teachers.models import Teacher
from admissions.services import active_school

from enterprise_ops.permissions import management_required
from enterprise_ops.services import audit
from .forms import (
    BiometricDeviceForm, CoverageAssignmentForm, SchoolDayEventForm, SchoolScheduleSettingsForm,
    TeacherAbsenceForm, TeacherBiometricIdentityForm, TimeSlotForm, TimetableEntryForm,
)
from .models import (
    BiometricDailySummary, BiometricDevice, ClassCoverage, SchoolDayEvent, SchoolScheduleSettings,
    TeacherAbsence, TeacherBiometricIdentity, TeacherBiometricPunch, TimeSlot, TimetableEntry,
)
from .workflow import (
    active_time_slots_queryset, build_print_context, build_schedule_settings_context,
    build_smart_builder_state, build_timetable_dashboard_context,
    create_absence_coverages, school_schedule_settings, section_schedule_queryset,
    substitute_teacher_is_unavailable, teacher_schedule_queryset,
    upcoming_coverages_queryset,
)


@management_required
def dashboard(request):
    builder_state = None
    if request.method == "POST" and request.POST.get("action") in {"builder_preview", "builder_apply"}:
        try:
            builder_state = build_smart_builder_state(request)
        except Exception as exc:
            detail = getattr(exc, "messages", [str(exc)])
            messages.error(
                request,
                f"لم يُعتمد الجدول وبقي الجدول السابق كما هو: {detail[0] if detail else 'تعارض غير متوقع'}.",
            )
            return redirect("timetable:dashboard")
        result = builder_state.get("builder_result")
        year = builder_state.get("builder_year")
        if year and builder_state.get("builder_apply") and result:
            audit(
                request, "create", "timetable.SmartBuilder", year.pk,
                f"اعتماد اقتراح الجدول الذكي ({result['variant_label']}): {len(result['created'])} حصة",
            )
            messages.success(
                request,
                f"تم اعتماد {len(result['created'])} حصة في عملية ذرية واحدة دون المساس بالحصص اليدوية.",
            )
            return redirect("timetable:dashboard")
    return render(request, "timetable/dashboard.html", build_timetable_dashboard_context(request, builder_state=builder_state))


@management_required
def smart_builder(request):
    """LEGACY/DEPRECATED for OPAL Update 131 only; no internal link may use it."""
    target = reverse("timetable:dashboard") + "#smart-builder"
    response = HttpResponseRedirect(target)
    response["Deprecation"] = "true"
    response["Sunset"] = "OPAL Update 132.0"
    response["Link"] = f'<{target}>; rel="successor-version"'
    return response


@management_required
def schedule_settings(request):
    school = active_school()
    settings = school_schedule_settings(school)
    event_id = request.POST.get("event_id") or request.GET.get("event")
    event_instance = (
        SchoolDayEvent.objects.filter(school=school, pk=event_id).first()
        if event_id else None
    )
    settings_form = SchoolScheduleSettingsForm(prefix="settings", instance=settings)
    event_form = SchoolDayEventForm(prefix="event", instance=event_instance, school=school)
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
            event_form = SchoolDayEventForm(
                request.POST,
                prefix="event",
                instance=event_instance,
                school=school,
            )
            if event_form.is_valid():
                with transaction.atomic():
                    event = event_form.save(commit=False)
                    event.school = school
                    event.save()
                    event_form.save_m2m()
                    audit(
                        request,
                        "update" if event_instance else "create",
                        "timetable.SchoolDayEvent",
                        event.pk,
                        f"{'تعديل' if event_instance else 'إضافة'} حدث اليوم المدرسي: {event.name}",
                    )
                messages.success(
                    request,
                    "تم تحديث الاستراحة ومجموعة الشعب." if event_instance
                    else "تمت إضافة الحدث إلى اليوم المدرسي.",
                )
                return redirect("timetable:schedule_settings")
    context = build_schedule_settings_context(
        school=school,
        settings_form=settings_form,
        event_form=event_form,
    )
    context["event_instance"] = event_instance
    return render(request, "timetable/schedule_settings.html", context)


@management_required
@require_POST
def event_delete(request, pk):
    event = get_object_or_404(SchoolDayEvent, pk=pk, school=active_school())
    event.delete()
    messages.success(request, "تم حذف الحدث من المؤقت.")
    return redirect("timetable:schedule_settings")


@management_required
def absence_center(request):
    school = active_school()
    form = TeacherAbsenceForm(request.POST or None)
    form.fields["teacher"].queryset = Teacher.objects.filter(school=school, is_active=True)
    if request.method == "POST" and form.is_valid():
        cleaned = form.cleaned_data
        try:
            with transaction.atomic():
                defaults = {
                    name: cleaned.get(name)
                    for name in [
                        "attendance_status", "arrival_time", "departure_time", "absence_type",
                        "reason", "is_approved", "payroll_approved", "deduction_amount", "payroll_notes",
                    ]
                }
                defaults["recorded_by"] = request.user
                defaults["approved_by"] = request.user if cleaned.get("is_approved") else None
                absence, created = TeacherAbsence.objects.update_or_create(
                    teacher=cleaned["teacher"], date=cleaned["date"], defaults=defaults,
                )
                absence.full_clean()
                absence.save()
                affected = create_absence_coverages(absence, school)
        except Exception as exc:
            form.add_error(None, str(exc))
        else:
            audit(
                request, "create" if created else "update", "timetable.TeacherAbsence", absence.pk,
                f"{'تسجيل' if created else 'تصحيح'} دوام {absence.teacher}: {absence.get_attendance_status_display()}",
            )
            messages.success(
                request,
                f"تم حفظ استثناء الدوام ومزامنة {len(affected)} حصة متأثرة دون إنشاء سجل حضور يومي.",
            )
            return redirect("timetable:absence_center")
    coverages = upcoming_coverages_queryset(school)
    exceptions = TeacherAbsence.objects.filter(teacher__school=school, date__gte=timezone.localdate()).select_related("teacher").order_by("date", "teacher__full_name")
    return render(request, "timetable/absence_center.html", {"form": form, "coverages": coverages, "exceptions": exceptions})


@management_required
def coverage_assign(request, pk):
    coverage = get_object_or_404(ClassCoverage.objects.select_related("entry__academic_year__school", "entry__time_slot"), pk=pk)
    form = CoverageAssignmentForm(request.POST or None, instance=coverage)
    form.fields["substitute_teacher"].queryset = Teacher.objects.filter(school=coverage.entry.academic_year.school, is_active=True).exclude(pk=coverage.entry.teacher_id)
    if request.method == "POST" and form.is_valid():
        substitute = form.cleaned_data["substitute_teacher"]
        if substitute_teacher_is_unavailable(coverage=coverage, substitute=substitute):
            form.add_error("substitute_teacher", "المعلم المختار مشغول بحصة أخرى أو مسجل غائبًا في هذا الوقت.")
        else:
            coverage = form.save(commit=False)
            coverage.status = "assigned"
            coverage.assigned_by = request.user
            coverage.save()
            messages.success(request, "تم تعيين المعلم البديل وإغلاق تنبيه الإشغال.")
            return redirect("timetable:absence_center")
    return render(request, "timetable/form.html", {"form": form, "title": "تعيين معلم بديل", "coverage": coverage})


@management_required
def entry_create(request):
    form = TimetableEntryForm(request.POST or None)
    if form.is_valid():
        entry = form.save()
        audit(request, "create", "timetable.TimetableEntry", entry.pk, f"إنشاء حصة: {entry}")
        messages.success(request, "تمت إضافة الحصة إلى الجدول.")
        return redirect("timetable:dashboard")
    return render(request, "timetable/form.html", {"form": form, "title": "إضافة حصة"})


@management_required
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


@management_required
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


@management_required
def slot_list(request):
    return render(request, "timetable/slot_list.html", {"slots": active_time_slots_queryset()})


@management_required
def slot_create(request):
    form = TimeSlotForm(request.POST or None)
    if form.is_valid():
        slot = form.save()
        audit(request, "create", "timetable.TimeSlot", slot.pk, f"إنشاء وقت حصة: {slot}")
        messages.success(request, "تمت إضافة وقت الحصة.")
        return redirect("timetable:slot_list")
    return render(request, "timetable/form.html", {"form": form, "title": "إضافة وقت حصة"})


@management_required
def slot_update(request, pk):
    slot = get_object_or_404(TimeSlot, pk=pk)
    if slot.generated_for_smart_schedule:
        messages.warning(request, "هذا الوقت مشتق من الجدول الذكي ولا يعدل يدويًا. أعد بناء الجدول بدلًا من ذلك.")
        return redirect("timetable:slot_list")
    form = TimeSlotForm(request.POST or None, instance=slot)
    if form.is_valid():
        form.save()
        audit(request, "update", "timetable.TimeSlot", slot.pk, f"تعديل وقت حصة: {slot}")
        messages.success(request, "تم تحديث وقت الحصة.")
        return redirect("timetable:slot_list")
    return render(request, "timetable/form.html", {"form": form, "title": "تعديل وقت حصة"})


@management_required
def slot_delete(request, pk):
    slot = get_object_or_404(TimeSlot, pk=pk)
    if request.method == "POST":
        if slot.generated_for_smart_schedule:
            messages.warning(request, "الوقت المشتق آليًا يحذف فقط عند إعادة بناء الجدول الذكي.")
        elif slot.entries.exists():
            messages.error(request, "لا يمكن حذف وقت مرتبط بحصص. أوقف تفعيله بدلًا من ذلك.")
        else:
            slot.delete()
            audit(request, "delete", "timetable.TimeSlot", pk, "حذف وقت حصة")
            messages.success(request, "تم حذف وقت الحصة.")
    return redirect("timetable:slot_list")


@management_required
def section_print(request, section_id):
    section = get_object_or_404(Section.objects.select_related("grade"), pk=section_id)
    entries = section_schedule_queryset(section)
    audit(request, "print", "timetable.SectionSchedule", section.pk, f"طباعة جدول {section}")
    return render(request, "timetable/print.html", build_print_context(entries, f"جدول {section}", school=section.academic_year.school))


@management_required
def teacher_print(request, teacher_id):
    teacher = get_object_or_404(Teacher, pk=teacher_id)
    entries = teacher_schedule_queryset(teacher)
    audit(request, "print", "timetable.TeacherSchedule", teacher.pk, f"طباعة جدول {teacher}")
    return render(request, "timetable/print.html", build_print_context(entries, f"جدول المعلم {teacher}", school=teacher.school))


@management_required
def biometric_center(request):
    school = active_school()
    selected_raw = (request.GET.get("date") or timezone.localdate().isoformat()).strip()
    try:
        selected_date = date.fromisoformat(selected_raw)
    except ValueError:
        selected_date = timezone.localdate()
    devices = BiometricDevice.objects.filter(school=school).select_related("branch").order_by("name")
    identities = TeacherBiometricIdentity.objects.filter(device__school=school).select_related("device", "teacher").order_by("teacher__full_name")
    summaries = BiometricDailySummary.objects.filter(teacher__school=school, date=selected_date).select_related(
        "teacher", "applied_exception", "reviewed_by"
    ).order_by("teacher__full_name")
    recent_punches = TeacherBiometricPunch.objects.filter(device__school=school).select_related("device", "teacher")[:50]
    one_time_token = request.session.pop("biometric_device_token_once", "")
    one_time_device = request.session.pop("biometric_device_token_device", "")
    return render(request, "timetable/biometric_center.html", {
        "selected_date": selected_date,
        "devices": devices,
        "identities": identities,
        "summaries": summaries,
        "recent_punches": recent_punches,
        "device_form": BiometricDeviceForm(school=school),
        "identity_form": TeacherBiometricIdentityForm(school=school),
        "one_time_token": one_time_token,
        "one_time_device": one_time_device,
    })


@management_required
@require_POST
def biometric_device_create(request):
    from .biometric_services import issue_device_token
    school = active_school()
    form = BiometricDeviceForm(request.POST, school=school)
    if not form.is_valid():
        messages.error(request, "تعذر إضافة جهاز البصمة: " + "; ".join(sum(form.errors.values(), [])))
        return redirect("timetable:biometric_center")
    device = form.save(commit=False)
    device.school = school
    device.save()
    raw_token = issue_device_token(device)
    request.session["biometric_device_token_once"] = raw_token
    request.session["biometric_device_token_device"] = device.name
    audit(request, "create", "timetable.BiometricDevice", device.pk, f"إضافة جهاز بصمة {device}")
    messages.success(request, "تم إضافة الجهاز. انسخ رمز الربط الظاهر مرة واحدة فقط.")
    return redirect("timetable:biometric_center")


@management_required
@require_POST
def biometric_device_token_regenerate(request, pk):
    from .biometric_services import issue_device_token
    device = get_object_or_404(BiometricDevice, pk=pk, school=active_school())
    raw_token = issue_device_token(device)
    request.session["biometric_device_token_once"] = raw_token
    request.session["biometric_device_token_device"] = device.name
    audit(request, "update", "timetable.BiometricDevice", device.pk, f"تدوير رمز ربط جهاز البصمة {device}")
    messages.success(request, "تم إنشاء رمز ربط جديد وأُلغي الرمز السابق.")
    return redirect("timetable:biometric_center")


@management_required
@require_POST
def biometric_identity_create(request):
    school = active_school()
    form = TeacherBiometricIdentityForm(request.POST, school=school)
    if form.is_valid():
        identity = form.save()
        audit(request, "create", "timetable.TeacherBiometricIdentity", identity.pk, f"ربط {identity.teacher} بجهاز {identity.device}")
        messages.success(request, "تم ربط معرف الجهاز بالمعلم.")
    else:
        messages.error(request, "تعذر حفظ الربط: " + "; ".join(sum(form.errors.values(), [])))
    return redirect("timetable:biometric_center")


@management_required
@require_POST
def biometric_sync(request):
    from .biometric_services import rebuild_daily_summaries
    raw = (request.POST.get("date") or timezone.localdate().isoformat()).strip()
    try:
        selected_date = date.fromisoformat(raw)
    except ValueError:
        selected_date = timezone.localdate()
    rows = rebuild_daily_summaries(selected_date, school=active_school())
    messages.success(request, f"تم تحديث ملخص البصمة لـ {len(rows)} معلمًا دون تعديل الدوام الرسمي تلقائيًا.")
    return redirect(f"{reverse('timetable:biometric_center')}?date={selected_date.isoformat()}")


@management_required
@require_POST
def biometric_summary_action(request, pk):
    from .biometric_services import apply_daily_summary, ignore_daily_summary
    summary = get_object_or_404(BiometricDailySummary.objects.select_related("teacher"), pk=pk, teacher__school=active_school())
    action = (request.POST.get("action") or "").strip()
    try:
        if action == "ignore":
            ignore_daily_summary(summary, user=request.user, note=request.POST.get("note", ""))
            messages.success(request, "تم تجاهل الاقتراح مع بقاء البصمات الخام محفوظة للمراجعة.")
        elif action == "apply":
            apply_daily_summary(summary, user=request.user, requested_status=request.POST.get("status", ""))
            messages.success(request, "تم اعتماد نتيجة البصمة في سجل دوام المعلم الرسمي ومزامنة الإشغال.")
        else:
            messages.error(request, "إجراء غير معروف.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages) if getattr(exc, "messages", None) else str(exc))
    return redirect(f"{reverse('timetable:biometric_center')}?date={summary.date.isoformat()}")
