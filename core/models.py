from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
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
        if self.is_closed:
            return "closed"
        if self.is_current:
            return "current"
        return "open"


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
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.code and self.academic_year_id:
            existing_codes = set(type(self).objects.filter(academic_year_id=self.academic_year_id).exclude(pk=self.pk).values_list("code", flat=True))
            self.code = "first" if "first" not in existing_codes else "second"
        self.full_clean(exclude=["is_current"])
        with transaction.atomic():
            if self.is_current and self.academic_year_id:
                type(self).objects.filter(academic_year_id=self.academic_year_id, is_current=True).exclude(pk=self.pk).update(is_current=False)
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.academic_year.name} - {self.get_code_display()}"


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
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
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
