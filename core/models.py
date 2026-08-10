from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.db.models import Q


class School(models.Model):
    name = models.CharField(max_length=200)
    official_name = models.CharField(max_length=250, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    logo = models.ImageField(upload_to="school_logos/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Branch(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="branches")
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    is_main = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="uniq_branch_per_school"),
        ]

    def __str__(self):
        return f"{self.school.name} - {self.name}"


class AcademicYear(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="academic_years")
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    midyear_break_start = models.DateField("بداية عطلة منتصف العام")
    midyear_break_end = models.DateField("نهاية عطلة منتصف العام")
    is_current = models.BooleanField(default=False)
    is_closed = models.BooleanField("عام مغلق", default=False, db_index=True)
    closed_at = models.DateTimeField("تاريخ الإغلاق", null=True, blank=True)
    closed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_academic_years",
        verbose_name="أغلقه",
    )
    closure_notes = models.TextField("ملاحظات الإغلاق", blank=True)
    prepared_at = models.DateTimeField("تاريخ تهيئة العام", null=True, blank=True)
    prepared_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prepared_academic_years",
        verbose_name="هيأه",
    )
    preparation_source = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="prepared_successors",
        verbose_name="عام التهيئة المصدر",
    )
    transition_completed_at = models.DateTimeField("تاريخ اكتمال الانتقال", null=True, blank=True)
    transition_completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_academic_year_transitions",
        verbose_name="منفذ الانتقال",
    )

    class Meta:
        ordering = ["-start_date", "name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="uniq_academic_year_per_school"),
            models.UniqueConstraint(
                fields=["school"],
                condition=Q(is_current=True),
                name="one_current_academic_year_per_school",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            errors["end_date"] = "تاريخ نهاية العام يجب أن يكون بعد تاريخ البداية."
        if self.start_date and self.midyear_break_start and self.midyear_break_start <= self.start_date:
            errors["midyear_break_start"] = "عطلة منتصف العام يجب أن تبدأ بعد بداية العام."
        if self.midyear_break_start and self.midyear_break_end and self.midyear_break_end < self.midyear_break_start:
            errors["midyear_break_end"] = "نهاية عطلة منتصف العام يجب ألا تسبق بدايتها."
        if self.end_date and self.midyear_break_end and self.midyear_break_end >= self.end_date:
            errors["midyear_break_end"] = "عطلة منتصف العام يجب أن تنتهي قبل نهاية العام."
        if self.is_closed and self.is_current:
            errors["is_current"] = "لا يمكن أن يكون العام المغلق هو العام الدراسي الحالي."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.start_date and self.end_date and (not self.midyear_break_start or not self.midyear_break_end):
            midpoint = self.start_date + timedelta(days=max((self.end_date - self.start_date).days // 2, 1))
            self.midyear_break_start = self.midyear_break_start or midpoint
            self.midyear_break_end = self.midyear_break_end or self.midyear_break_start
        self.full_clean(exclude=["is_current"])
        with transaction.atomic():
            if self.is_current and self.school_id:
                type(self).objects.filter(school_id=self.school_id, is_current=True).exclude(pk=self.pk).update(is_current=False)
            result = super().save(*args, **kwargs)
            self.ensure_semesters()
            return result

    def ensure_semesters(self):
        if not all([self.start_date, self.end_date, self.midyear_break_start, self.midyear_break_end]):
            return
        Semester.objects.update_or_create(
            academic_year=self,
            code="first",
            defaults={
                "name": "الفصل الدراسي الأول",
                "start_date": self.start_date,
                "end_date": self.midyear_break_start - timedelta(days=1),
            },
        )
        Semester.objects.update_or_create(
            academic_year=self,
            code="second",
            defaults={
                "name": "الفصل الدراسي الثاني",
                "start_date": self.midyear_break_end + timedelta(days=1),
                "end_date": self.end_date,
            },
        )
        self.semesters.exclude(code__in=["first", "second"]).delete()

    def __str__(self):
        return self.name

    @property
    def operational_status(self):
        try:
            self.financial_closure
            return "financial_archived"
        except (AttributeError, ObjectDoesNotExist):
            pass
        if self.is_closed:
            return "academic_closed"
        if self.is_current:
            return "current"
        if self.prepared_at:
            return "ready"
        return "upcoming"

    @property
    def operational_status_label(self):
        return {
            "upcoming": "قادم غير مهيأ",
            "ready": "مهيأ وجاهز",
            "current": "حالي",
            "academic_closed": "مغلق أكاديميًا",
            "financial_archived": "مؤرشف ماليًا",
        }[self.operational_status]


class Semester(models.Model):
    TERM_CHOICES = [
        ("first", "الفصل الدراسي الأول"),
        ("second", "الفصل الدراسي الثاني"),
    ]

    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="semesters")
    code = models.CharField(max_length=10, choices=TERM_CHOICES)
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    is_closed = models.BooleanField("فصل مغلق أكاديميًا", default=False, db_index=True)
    closed_at = models.DateTimeField("تاريخ إغلاق الفصل", null=True, blank=True)
    closed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_semesters",
        verbose_name="أغلقه",
    )
    closure_notes = models.TextField("ملاحظات إغلاق الفصل", blank=True)

    class Meta:
        ordering = ["academic_year__start_date", "code"]
        constraints = [
            models.UniqueConstraint(fields=["academic_year", "code"], name="uniq_semester_code_per_year"),
            models.UniqueConstraint(
                fields=["academic_year"],
                condition=Q(is_current=True),
                name="one_current_semester_per_academic_year",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors["end_date"] = "تاريخ نهاية الفصل يجب ألا يسبق تاريخ البداية."
        if self.academic_year_id:
            if self.start_date and self.start_date < self.academic_year.start_date:
                errors["start_date"] = "الفصل لا يمكن أن يبدأ قبل العام الدراسي."
            if self.end_date and self.end_date > self.academic_year.end_date:
                errors["end_date"] = "الفصل لا يمكن أن ينتهي بعد العام الدراسي."
        if self.is_closed and self.is_current:
            errors["is_current"] = "لا يمكن أن يكون الفصل المغلق هو الفصل النشط."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.code and self.academic_year_id:
            existing_codes = set(type(self).objects.filter(academic_year_id=self.academic_year_id).exclude(pk=self.pk).values_list("code", flat=True))
            self.code = "first" if "first" not in existing_codes else "second"
        if self.is_closed:
            self.is_current = False
        self.full_clean(exclude=["is_current"])
        with transaction.atomic():
            if self.is_current and self.academic_year_id:
                type(self).objects.filter(academic_year_id=self.academic_year_id, is_current=True).exclude(pk=self.pk).update(is_current=False)
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.academic_year.name} - {self.get_code_display()}"


class SemesterStructureSnapshot(models.Model):
    """Historical term structure while live operations keep their canonical models."""

    semester = models.OneToOneField(
        Semester,
        on_delete=models.PROTECT,
        related_name="structure_snapshot",
        verbose_name="الفصل الدراسي",
    )
    source_snapshot = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_snapshots",
        verbose_name="لقطة الفصل المصدر",
    )
    payload = models.JSONField("بيانات البنية التاريخية", default=dict)
    is_final = models.BooleanField("لقطة إغلاق نهائية", default=False, db_index=True)
    captured_at = models.DateTimeField("وقت الالتقاط", auto_now=True)
    captured_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="captured_semester_structures",
        verbose_name="التقطها",
    )

    class Meta:
        ordering = ["semester__academic_year__start_date", "semester__code"]

    def __str__(self):
        return f"لقطة بنية {self.semester}"


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("create", "إنشاء"),
        ("update", "تعديل"),
        ("delete", "حذف"),
        ("login", "تسجيل دخول"),
        ("logout", "تسجيل خروج"),
        ("view", "عرض"),
        ("print", "طباعة"),
        ("export", "تصدير"),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    school = models.ForeignKey(
        School,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    result = models.CharField(max_length=30, default="success", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} - {self.model_name} - {self.created_at}"


class Sequence(models.Model):
    key = models.CharField(max_length=50, unique=True)
    prefix = models.CharField(max_length=20)
    current_number = models.PositiveIntegerField(default=0)
    padding = models.PositiveIntegerField(default=6)
    yearly_reset = models.BooleanField(default=True)

    def __str__(self):
        return self.key


class DataIntegrityRun(models.Model):
    MODE_CHOICES = [("scan", "فحص فقط"), ("fix_safe", "فحص وإصلاح آمن")]
    school = models.ForeignKey(
        School,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integrity_runs",
    )
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="scan")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="integrity_runs")
    total_issues = models.PositiveIntegerField(default=0)
    critical_count = models.PositiveIntegerField(default=0)
    warning_count = models.PositiveIntegerField(default=0)
    fixed_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"فحص سلامة #{self.pk} - {self.get_mode_display()}"


class DataIntegrityIssue(models.Model):
    SEVERITY_CHOICES = [("critical", "حرج"), ("warning", "تحذير"), ("info", "معلومة")]
    run = models.ForeignKey(DataIntegrityRun, on_delete=models.CASCADE, related_name="issues")
    code = models.CharField(max_length=80, db_index=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="warning")
    model_name = models.CharField(max_length=120, blank=True)
    object_id = models.CharField(max_length=250, blank=True)
    description = models.TextField()
    is_fixable = models.BooleanField(default=False)
    is_fixed = models.BooleanField(default=False)
    resolution = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["severity", "code", "id"]
        indexes = [models.Index(fields=["run", "severity", "is_fixed"])]

    def __str__(self):
        return f"{self.code}: {self.description[:80]}"


class ProductionDataResetRun(models.Model):
    """Auditable preview/execution record for the production data reset workflow."""

    class Status(models.TextChoices):
        PREVIEWED = "previewed", "تمت المعاينة"
        RUNNING = "running", "قيد التنفيذ"
        SUCCEEDED = "succeeded", "مكتمل"
        FAILED = "failed", "فشل"

    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="production_data_reset_runs",
        verbose_name="المدير المنفذ",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PREVIEWED, db_index=True)
    preview_counts = models.JSONField(default=dict, blank=True)
    deleted_counts = models.JSONField(default=dict, blank=True)
    remaining_counts = models.JSONField(default=dict, blank=True)
    preserved_summary = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "سجل تهيئة التشغيل الفعلي"
        verbose_name_plural = "سجلات تهيئة التشغيل الفعلي"

    def __str__(self):
        return f"تهيئة التشغيل الفعلي #{self.pk or '-'} — {self.get_status_display()}"


class SystemMobileAPIToken(models.Model):
    """Hashed bearer token for the native OPAL ERP mobile application."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="opal_system_mobile_tokens",
    )
    token_hash = models.CharField(max_length=128, unique=True, db_index=True)
    token_prefix = models.CharField(max_length=16, db_index=True)
    device_name = models.CharField(max_length=120, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "revoked_at", "expires_at"], name="core_system_user_id_4d66b3_idx")]
        verbose_name = "رمز تطبيق نظام أوبال"
        verbose_name_plural = "رموز تطبيق نظام أوبال"

    @property
    def is_active(self):
        from django.utils import timezone

        return self.revoked_at is None and self.expires_at > timezone.now() and self.user.is_active

    def __str__(self):
        return f"{self.user.get_username()} · {self.token_prefix}"
