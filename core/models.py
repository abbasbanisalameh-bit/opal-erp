from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.contrib.auth.models import User


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

    def __str__(self):
        return f"{self.school.name} - {self.name}"


class AcademicYear(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="academic_years")
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["school"],
                condition=Q(is_current=True),
                name="one_current_academic_year_per_school",
            )
        ]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": "تاريخ نهاية العام يجب أن يكون بعد تاريخ البداية."})

    def save(self, *args, **kwargs):
        self.full_clean(exclude=["is_current"])
        with transaction.atomic():
            if self.is_current and self.school_id:
                type(self).objects.filter(school_id=self.school_id, is_current=True).exclude(pk=self.pk).update(is_current=False)
            return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Semester(models.Model):
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="semesters")
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ["academic_year__start_date", "start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year"],
                condition=Q(is_current=True),
                name="one_current_semester_per_academic_year",
            )
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            errors["end_date"] = "تاريخ نهاية الفصل يجب أن يكون بعد تاريخ البداية."
        if self.academic_year_id:
            if self.start_date and self.start_date < self.academic_year.start_date:
                errors["start_date"] = "الفصل لا يمكن أن يبدأ قبل العام الدراسي."
            if self.end_date and self.end_date > self.academic_year.end_date:
                errors["end_date"] = "الفصل لا يمكن أن ينتهي بعد العام الدراسي."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean(exclude=["is_current"])
        with transaction.atomic():
            if self.is_current and self.academic_year_id:
                type(self).objects.filter(academic_year_id=self.academic_year_id, is_current=True).exclude(pk=self.pk).update(is_current=False)
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.academic_year.name} - {self.name}"


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
