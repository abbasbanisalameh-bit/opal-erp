from datetime import datetime

from django.utils import timezone

from academics.models import Enrollment

from .models import SchoolDayEvent, SchoolScheduleSettings, TimeSlot, TimetableEntry


DAY_CODES = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"}


def _now_parts(now=None):
    now = timezone.localtime(now or timezone.now())
    return now, DAY_CODES[now.weekday()], now.time().replace(tzinfo=None)


def _event_rows(school, day):
    rows = []
    for event in SchoolDayEvent.objects.filter(school=school, is_active=True):
        if day in {item.strip() for item in event.days.split(",")}:
            rows.append({"name": event.name, "start": event.start_time, "end": event.end_time, "kind": event.event_type})
    for slot in TimeSlot.objects.filter(is_active=True):
        rows.append({"name": slot.name, "start": slot.start_time, "end": slot.end_time, "kind": "class"})
    return sorted(rows, key=lambda row: (row["start"], row["end"]))


def school_live_status(school, now=None, *, guardian=False):
    now, day, current_time = _now_parts(now)
    settings = SchoolScheduleSettings.objects.filter(school=school).first() or SchoolScheduleSettings(school=school)
    if day in settings.weekend_day_codes:
        return {"state": "weekend", "message": "عطلة نهاية أسبوع سعيدة. اعتنوا بأبنائنا جيدًا." if guardian else "عطلة نهاية أسبوع سعيدة", "current": None, "next": None}
    rows = _event_rows(school, day)
    current = next((row for row in rows if row["start"] <= current_time < row["end"]), None)
    following = next((row for row in rows if row["start"] > current_time), None)
    status = {"state": "active" if current else "between", "current": current, "next": following, "message": ""}
    if current:
        end_at = timezone.make_aware(datetime.combine(now.date(), current["end"]), timezone.get_current_timezone())
        status["seconds_remaining"] = max(int((end_at - now).total_seconds()), 0)
        status["ends_soon"] = status["seconds_remaining"] <= settings.alert_minutes_before_end * 60
        status["message"] = f"الحدث الجاري: {current['name']}"
    elif following:
        status["message"] = f"الحدث التالي: {following['name']}"
    else:
        status.update({"state": "finished", "message": "خارج وقت الدوام"})
    return status


def teacher_live_status(teacher, now=None):
    now, day, current_time = _now_parts(now)
    base = school_live_status(teacher.school, now)
    if base["state"] == "weekend":
        return base
    entries = list(TimetableEntry.objects.filter(
        teacher=teacher, day=day, is_active=True, academic_year__is_current=True,
    ).select_related("section", "subject", "time_slot").order_by("time_slot__start_time"))
    current = next((row for row in entries if row.time_slot.start_time <= current_time < row.time_slot.end_time), None)
    following = next((row for row in entries if row.time_slot.start_time > current_time), None)
    return {**base, "current_class": current, "next_class": following,
            "teacher_message": (f"الحصة الحالية: {current.section}" if current else "الحصة الحالية: فراغ"),
            "teacher_next_message": (f"الحصة التالية: {following.section}" if following else "لا توجد حصة تالية")}


def student_live_status(student, now=None):
    enrollment = Enrollment.objects.filter(student=student, status="active").select_related("academic_year__school", "section").order_by("-academic_year__start_date").first()
    if not enrollment or not enrollment.section_id:
        return {"state": "unavailable", "message": "لا يوجد جدول دراسي فعال"}
    now, day, current_time = _now_parts(now)
    base = school_live_status(enrollment.academic_year.school, now, guardian=True)
    if base["state"] == "weekend":
        return base
    entries = list(TimetableEntry.objects.filter(
        section=enrollment.section, academic_year=enrollment.academic_year, day=day, is_active=True,
    ).select_related("subject", "teacher", "time_slot").order_by("time_slot__start_time"))
    current = next((row for row in entries if row.time_slot.start_time <= current_time < row.time_slot.end_time), None)
    following = next((row for row in entries if row.time_slot.start_time > current_time), None)
    if not current and not following and entries:
        base.update({"state": "finished", "message": "انتهى دوام الطالب"})
    return {**base, "current_class": current, "next_class": following}


def management_live_status(school, now=None):
    now, day, current_time = _now_parts(now)
    base = school_live_status(school, now)
    entries = TimetableEntry.objects.filter(
        academic_year__school=school, academic_year__is_current=True, day=day, is_active=True,
        time_slot__start_time__lte=current_time, time_slot__end_time__gt=current_time,
    ).select_related("teacher", "section", "subject", "time_slot")
    return {**base, "current_entries": entries, "busy_teachers": entries.exclude(teacher=None).count()}
