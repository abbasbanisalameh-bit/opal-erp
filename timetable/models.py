from django.core.exceptions import ValidationError
from django.apps import apps
from django.db import models
from django.db.models import Q



class TimeSlot(models.Model):
    name = models.CharField(max_length=50)
    start_time = models.TimeField()
    end_time = models.TimeField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    generated_for_smart_schedule = models.BooleanField(
        "وقت مشتق آليًا", default=False, db_index=True, editable=False
    )

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

    academic_year = models.ForeignKey("core.AcademicYear", on_delete=models.CASCADE)
    section = models.ForeignKey("academics.Section", on_delete=models.CASCADE, related_name="timetable_entries")
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT)
    teacher = models.ForeignKey("teachers.Teacher", on_delete=models.SET_NULL, null=True, blank=True, related_name="timetable_entries")
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
        if self.subject_id and self.academic_year_id and self.subject.academic_year_id != self.academic_year_id:
            errors["subject"] = "المادة لا تتبع العام الدراسي المحدد."

        base = TimetableEntry.objects.exclude(pk=self.pk).filter(
            academic_year_id=self.academic_year_id,
            day=self.day,
            is_active=True,
        )
        if self.time_slot_id:
            base = base.filter(
                time_slot__start_time__lt=self.time_slot.end_time,
                time_slot__end_time__gt=self.time_slot.start_time,
            )
        if self.section_id and base.filter(section_id=self.section_id).exists():
            errors["section"] = "يوجد حصة أخرى لهذه الشعبة تتداخل مع هذا الوقت."
        if self.teacher_id and base.filter(teacher_id=self.teacher_id).exists():
            errors["teacher"] = "المعلم مرتبط بحصة أخرى تتداخل مع هذا الوقت."
        if self.room and base.filter(room__iexact=self.room).exists():
            errors["room"] = "الغرفة مستخدمة في حصة أخرى تتداخل مع هذا الوقت."

        if self.teacher_id and self.section_id and self.subject_id and self.academic_year_id:
            teacher_assignment_model = apps.get_model("teachers", "TeacherAssignment")
            assignments = teacher_assignment_model.objects.filter(
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
    weekend_days = models.CharField("أيام العطلة", max_length=100, default="friday,saturday")
    alert_minutes_before_end = models.PositiveSmallIntegerField("التنبيه قبل نهاية الحدث بالدقائق", default=5)
    updated_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def weekend_day_codes(self):
        return {item.strip() for item in self.weekend_days.split(",") if item.strip()}


class SchoolDayEvent(models.Model):
    EVENT_TYPES = [("assembly", "طابور صباحي"), ("break", "استراحة"), ("dismissal", "نهاية دوام"), ("other", "حدث آخر")]
    PLACEMENT_MODES = [("fixed", "وقت ثابت"), ("smart", "يوزعه النظام بذكاء")]

    school = models.ForeignKey("core.School", on_delete=models.CASCADE, related_name="day_events")
    name = models.CharField("اسم الحدث", max_length=120)
    event_type = models.CharField("نوع الحدث", max_length=20, choices=EVENT_TYPES, default="other")
    start_time = models.TimeField("وقت البداية", null=True, blank=True)
    end_time = models.TimeField("وقت النهاية", null=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(
        "المدة بالدقائق", null=True, blank=True,
        help_text="مطلوبة للاستراحة الذكية، ويحسب النظام وقتها بين الحصص.",
    )
    placement_mode = models.CharField(
        "طريقة تحديد الوقت", max_length=20, choices=PLACEMENT_MODES, default="fixed"
    )
    sections = models.ManyToManyField(
        "academics.Section", blank=True, related_name="school_day_events",
        verbose_name="الشعب التابعة للاستراحة",
        help_text="اتركها فارغة فقط للأحداث العامة التي تشمل المدرسة كلها.",
    )
    days = models.CharField("أيام التطبيق", max_length=120, default="sunday,monday,tuesday,wednesday,thursday")
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "start_time", "name"]

    @property
    def day_codes(self):
        return {item.strip() for item in self.days.split(",") if item.strip()}

    @property
    def effective_duration_minutes(self):
        if self.duration_minutes:
            return self.duration_minutes
        if self.start_time and self.end_time:
            start = self.start_time.hour * 60 + self.start_time.minute
            end = self.end_time.hour * 60 + self.end_time.minute
            return max(end - start, 0)
        return 0

    def clean(self):
        super().clean()
        errors = {}
        if self.event_type == "break":
            if not self.duration_minutes or not 5 <= self.duration_minutes <= 60:
                errors["duration_minutes"] = "مدة الاستراحة يجب أن تكون بين 5 و60 دقيقة."
            if self.placement_mode == "fixed" and (not self.start_time or not self.end_time):
                errors["start_time"] = "حدد وقت بداية الاستراحة الثابتة؛ يحسب النظام وقت النهاية من المدة."
        elif not self.start_time or not self.end_time:
            errors["start_time"] = "الأحداث غير الاستراحة الذكية تحتاج وقت بداية ونهاية."
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            errors["end_time"] = "وقت النهاية يجب أن يكون بعد البداية."
        if self.duration_minutes and not 5 <= self.duration_minutes <= 60:
            errors["duration_minutes"] = "المدة يجب أن تكون بين 5 و60 دقيقة."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name


class TeacherAbsence(models.Model):
    """The single daily work-attendance record for a teacher.

    The historic model name is retained so existing timetable, payroll and
    coverage records remain in place.  It now records the full official work
    status (arrival, departure and authorised exceptions) instead of creating
    a parallel attendance system.
    """

    ABSENCE_TYPES = [
        ("excused", "غياب مبرر"),
        ("unexcused", "غياب غير مبرر"),
    ]
    ATTENDANCE_STATUSES = [
        ("present", "منتظم"),
        ("late", "متأخر"),
        ("early_departure", "مغادرة مبكرة"),
        ("absent", "غائب"),
        ("approved_excuse", "عذر معتمد"),
        ("official_mission", "مهمة رسمية"),
    ]

    teacher = models.ForeignKey("teachers.Teacher", on_delete=models.CASCADE, related_name="schedule_absences")
    date = models.DateField(db_index=True)
    attendance_status = models.CharField(
        "حالة الدوام",
        max_length=30,
        choices=ATTENDANCE_STATUSES,
        default="absent",
        db_index=True,
    )
    arrival_time = models.TimeField("وقت القدوم", null=True, blank=True)
    departure_time = models.TimeField("وقت المغادرة", null=True, blank=True)
    reason = models.CharField(max_length=200, blank=True)
    absence_type = models.CharField(max_length=20, choices=ABSENCE_TYPES, default="excused", db_index=True)
    is_approved = models.BooleanField("استثناء معتمد", default=False, db_index=True)
    approved_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_teacher_work_records",
    )
    payroll_approved = models.BooleanField("معتمد للخصم من الراتب", default=False, db_index=True)
    deduction_amount = models.DecimalField("قيمة الخصم", max_digits=10, decimal_places=2, default=0)
    payroll_notes = models.CharField("ملاحظات الخصم", max_length=250, blank=True)
    recorded_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["teacher", "date"], name="uniq_teacher_absence_date")]

    def clean(self):
        super().clean()
        errors = {}
        if self.deduction_amount is not None and self.deduction_amount < 0:
            errors["deduction_amount"] = "قيمة الخصم لا يمكن أن تكون سالبة."
        if self.payroll_approved and self.absence_type != "unexcused":
            errors["payroll_approved"] = "لا يعتمد للخصم إلا الغياب غير المبرر."
        if self.departure_time and self.arrival_time and self.departure_time <= self.arrival_time:
            errors["departure_time"] = "وقت المغادرة يجب أن يكون بعد وقت القدوم."
        if self.attendance_status in {"approved_excuse", "official_mission"} and not self.is_approved:
            errors["is_approved"] = "لا يعتمد العذر أو المهمة الرسمية قبل الموافقة عليه."
        if self.attendance_status in {"present", "late", "early_departure"} and self.payroll_approved:
            errors["payroll_approved"] = "لا يمكن اعتماد خصم راتب لحالة دوام غير غياب."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean(exclude=["recorded_by"])
        return super().save(*args, **kwargs)


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


class BiometricDevice(models.Model):
    """A physical attendance terminal registered with OPAL.

    OPAL never stores fingerprint templates.  The terminal keeps the biometric
    material; OPAL stores only the external user id and punch timestamps.
    """

    VENDORS = [
        ("generic", "جهاز عام / بوابة محلية"),
        ("zkteco", "ZKTeco"),
        ("other", "شركة أخرى"),
    ]

    school = models.ForeignKey("core.School", on_delete=models.CASCADE, related_name="biometric_devices")
    branch = models.ForeignKey(
        "core.Branch", on_delete=models.SET_NULL, null=True, blank=True, related_name="biometric_devices"
    )
    name = models.CharField("اسم الجهاز", max_length=120)
    device_code = models.CharField("رمز الجهاز", max_length=80, unique=True)
    vendor = models.CharField("الشركة", max_length=20, choices=VENDORS, default="generic")
    serial_number = models.CharField("الرقم التسلسلي", max_length=120, blank=True)
    timezone_name = models.CharField("المنطقة الزمنية", max_length=64, default="Asia/Amman")
    token_hash = models.CharField("بصمة رمز الربط", max_length=64, unique=True, null=True, blank=True, editable=False)
    token_hint = models.CharField("آخر أحرف الرمز", max_length=8, blank=True, editable=False)
    is_active = models.BooleanField("فعال", default=True, db_index=True)
    last_seen_at = models.DateTimeField("آخر اتصال", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["school__name", "name"]
        verbose_name = "جهاز بصمة"
        verbose_name_plural = "أجهزة البصمة"

    def clean(self):
        super().clean()
        if self.branch_id and self.school_id and self.branch.school_id != self.school_id:
            raise ValidationError({"branch": "الفرع لا يتبع مدرسة جهاز البصمة."})

    def save(self, *args, **kwargs):
        self.device_code = (self.device_code or "").strip().upper()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.device_code})"


class TeacherBiometricIdentity(models.Model):
    """Maps a terminal-local numeric/string user id to the canonical Teacher."""

    device = models.ForeignKey(BiometricDevice, on_delete=models.CASCADE, related_name="teacher_identities")
    teacher = models.ForeignKey("teachers.Teacher", on_delete=models.CASCADE, related_name="biometric_identities")
    device_user_id = models.CharField("معرف المعلم داخل الجهاز", max_length=80)
    is_active = models.BooleanField("فعال", default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["teacher__full_name", "device_user_id"]
        constraints = [
            models.UniqueConstraint(fields=["device", "device_user_id"], name="uniq_biometric_device_user"),
            models.UniqueConstraint(fields=["device", "teacher"], name="uniq_biometric_device_teacher"),
        ]

    def clean(self):
        super().clean()
        if self.device_id and self.teacher_id and self.device.school_id != self.teacher.school_id:
            raise ValidationError("المعلم وجهاز البصمة يجب أن يتبعا المدرسة نفسها.")

    def save(self, *args, **kwargs):
        self.device_user_id = (self.device_user_id or "").strip()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.teacher} — {self.device}: {self.device_user_id}"


class TeacherBiometricPunch(models.Model):
    DIRECTIONS = [
        ("in", "دخول"),
        ("out", "خروج"),
        ("unknown", "غير محدد"),
    ]

    device = models.ForeignKey(BiometricDevice, on_delete=models.PROTECT, related_name="punches")
    teacher = models.ForeignKey(
        "teachers.Teacher", on_delete=models.SET_NULL, null=True, blank=True, related_name="biometric_punches"
    )
    device_user_id = models.CharField("معرف المستخدم في الجهاز", max_length=80, db_index=True)
    event_uid = models.CharField("معرف الحدث", max_length=64, unique=True, db_index=True)
    punched_at = models.DateTimeField("وقت البصمة", db_index=True)
    direction = models.CharField("نوع الحركة", max_length=10, choices=DIRECTIONS, default="unknown", db_index=True)
    raw_payload = models.JSONField("بيانات الجهاز الخام", default=dict, blank=True)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-punched_at", "-id"]
        indexes = [
            models.Index(fields=["teacher", "punched_at"], name="bio_teacher_punch_idx"),
            models.Index(fields=["device", "punched_at"], name="bio_device_punch_idx"),
        ]

    def __str__(self):
        who = self.teacher or self.device_user_id
        return f"{who} — {self.punched_at}"


class BiometricDailySummary(models.Model):
    DERIVED_STATUSES = [
        ("normal", "منتظم"),
        ("late", "متأخر"),
        ("early_departure", "مغادرة مبكرة"),
        ("late_and_early", "تأخر ومغادرة مبكرة"),
        ("incomplete", "بصمة واحدة / غير مكتمل"),
        ("no_punch", "لا توجد بصمة"),
        ("no_schedule", "لا يوجد جدول في هذا اليوم"),
    ]
    REVIEW_STATUSES = [
        ("pending", "بانتظار المراجعة"),
        ("applied", "اعتمد في الدوام"),
        ("ignored", "تم التجاهل"),
    ]

    teacher = models.ForeignKey("teachers.Teacher", on_delete=models.CASCADE, related_name="biometric_daily_summaries")
    date = models.DateField("التاريخ", db_index=True)
    first_punch_at = models.DateTimeField("أول بصمة", null=True, blank=True)
    last_punch_at = models.DateTimeField("آخر بصمة", null=True, blank=True)
    expected_start = models.TimeField("بداية الدوام المتوقعة", null=True, blank=True)
    expected_end = models.TimeField("نهاية الدوام المتوقعة", null=True, blank=True)
    punch_count = models.PositiveSmallIntegerField("عدد البصمات", default=0)
    source_devices_count = models.PositiveSmallIntegerField("عدد الأجهزة", default=0)
    derived_status = models.CharField("النتيجة المقترحة", max_length=24, choices=DERIVED_STATUSES, db_index=True)
    review_status = models.CharField("حالة المراجعة", max_length=12, choices=REVIEW_STATUSES, default="pending", db_index=True)
    applied_exception = models.ForeignKey(
        TeacherAbsence, on_delete=models.SET_NULL, null=True, blank=True, related_name="biometric_summaries"
    )
    reviewed_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_biometric_summaries"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField("ملاحظة", max_length=250, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "teacher__full_name"]
        constraints = [
            models.UniqueConstraint(fields=["teacher", "date"], name="uniq_biometric_teacher_day_summary"),
        ]
        indexes = [
            models.Index(fields=["date", "derived_status", "review_status"], name="bio_daily_review_idx"),
        ]

    def __str__(self):
        return f"{self.teacher} — {self.date}: {self.get_derived_status_display()}"
