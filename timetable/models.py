from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from academics.models import Section, Subject
from core.models import AcademicYear
from teachers.models import Teacher, TeacherAssignment


class TimeSlot(models.Model):
    name = models.CharField(max_length=50)
    start_time = models.TimeField()
    end_time = models.TimeField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "start_time"]

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "وقت نهاية الحصة يجب أن يكون بعد وقت البداية."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class TimetableEntry(models.Model):
    DAYS = [
        ("saturday", "السبت"),
        ("sunday", "الأحد"),
        ("monday", "الاثنين"),
        ("tuesday", "الثلاثاء"),
        ("wednesday", "الأربعاء"),
        ("thursday", "الخميس"),
        ("friday", "الجمعة"),
    ]

    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="timetable_entries")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name="timetable_entries")
    day = models.CharField(max_length=20, choices=DAYS)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name="entries")
    room = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    generated_automatically = models.BooleanField(default=False, db_index=True)

    class Meta:
        unique_together = ("academic_year", "section", "day", "time_slot")
        ordering = ["day", "time_slot__order", "section__grade__order", "section__name"]
        indexes = [
            models.Index(fields=["academic_year", "day"]),
            models.Index(fields=["teacher", "day"]),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.academic_year_id and self.academic_year.is_closed:
            errors["academic_year"] = "العام الدراسي مغلق ولا يقبل تعديل الجدول."
        if self.section_id and self.section.academic_year_id and self.academic_year_id != self.section.academic_year_id:
            errors["section"] = "الشعبة المختارة لا تتبع العام الدراسي المحدد."
        if self.section_id and self.subject_id and self.subject.grade_id and self.subject.grade_id != self.section.grade_id:
            errors["subject"] = "المادة لا تتبع صف الشعبة المختارة."

        base = TimetableEntry.objects.exclude(pk=self.pk).filter(
            academic_year_id=self.academic_year_id,
            day=self.day,
            time_slot_id=self.time_slot_id,
            is_active=True,
        )
        if self.section_id and base.filter(section_id=self.section_id).exists():
            errors["section"] = "يوجد حصة أخرى لهذه الشعبة في الوقت نفسه."
        if self.teacher_id and base.filter(teacher_id=self.teacher_id).exists():
            errors["teacher"] = "المعلم مرتبط بحصة أخرى في الوقت نفسه."
        if self.room and base.filter(room__iexact=self.room).exists():
            errors["room"] = "الغرفة مستخدمة في حصة أخرى في الوقت نفسه."

        if self.teacher_id and self.section_id and self.subject_id and self.academic_year_id:
            assignments = TeacherAssignment.objects.filter(
                teacher_id=self.teacher_id,
                academic_year_id=self.academic_year_id,
                is_active=True,
            )
            if assignments.exists() and not assignments.filter(
                section_id=self.section_id,
                subject_id=self.subject_id,
            ).exists():
                errors["teacher"] = "لا يوجد تكليف فعّال لهذا المعلم بهذه المادة والشعبة."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.section} - {self.subject} - {self.get_day_display()}"


class SchoolScheduleSettings(models.Model):
    school = models.OneToOneField("core.School", on_delete=models.CASCADE, related_name="schedule_settings")
    weekend_days = models.CharField("أيام العطلة", max_length=100, default="thursday,friday")
    alert_minutes_before_end = models.PositiveSmallIntegerField("التنبيه قبل نهاية الحدث بالدقائق", default=5)
    updated_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def weekend_day_codes(self):
        return {item.strip() for item in self.weekend_days.split(",") if item.strip()}


class SchoolDayEvent(models.Model):
    EVENT_TYPES = [("assembly", "طابور صباحي"), ("break", "استراحة"), ("dismissal", "نهاية دوام"), ("other", "حدث آخر")]
    school = models.ForeignKey("core.School", on_delete=models.CASCADE, related_name="day_events")
    name = models.CharField("اسم الحدث", max_length=120)
    event_type = models.CharField("نوع الحدث", max_length=20, choices=EVENT_TYPES, default="other")
    start_time = models.TimeField("وقت البداية")
    end_time = models.TimeField("وقت النهاية")
    days = models.CharField("أيام التطبيق", max_length=120, default="saturday,sunday,monday,tuesday,wednesday")
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "start_time"]

    def clean(self):
        super().clean()
        if self.end_time <= self.start_time:
            raise ValidationError({"end_time": "وقت النهاية يجب أن يكون بعد البداية."})

    def __str__(self):
        return self.name


class TeacherAbsence(models.Model):
    teacher = models.ForeignKey("teachers.Teacher", on_delete=models.CASCADE, related_name="schedule_absences")
    date = models.DateField(db_index=True)
    reason = models.CharField(max_length=200, blank=True)
    recorded_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["teacher", "date"], name="uniq_teacher_absence_date")]


class ClassCoverage(models.Model):
    STATUS = [("needed", "بحاجة إشغال"), ("assigned", "تم تعيين بديل"), ("cancelled", "ملغاة")]
    entry = models.ForeignKey(TimetableEntry, on_delete=models.CASCADE, related_name="coverage_records")
    date = models.DateField(db_index=True)
    substitute_teacher = models.ForeignKey("teachers.Teacher", on_delete=models.SET_NULL, null=True, blank=True, related_name="substitute_coverages")
    status = models.CharField(max_length=20, choices=STATUS, default="needed", db_index=True)
    assigned_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["entry", "date"], name="uniq_entry_coverage_date")]
