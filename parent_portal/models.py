from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from core.identifiers import normalize_identifier, normalize_phone


class Family(models.Model):
    IDENTITY_TYPES = [
        ("national", "رقم وطني أردني"),
        ("personal", "رقم شخصي لغير الأردني"),
        ("other", "معرف آخر"),
    ]
    SOURCE_CHOICES = [
        ("manual", "إدخال OPAL"),
        ("openemis", "OpenEMIS"),
    ]
    FINANCIAL_POLICY_CHOICES = [
        ("alert_only", "تنبيه فقط دون حجب"),
        ("hide_results", "حجب النتائج فقط"),
        ("hide_certificates", "حجب الشهادات والوثائق فقط"),
        ("restrict_noncritical", "تقييد الخدمات غير الأساسية"),
        ("exceptional_suspension", "تعليق استثنائي بقرار الإدارة"),
    ]

    school = models.ForeignKey(
        "core.School",
        on_delete=models.CASCADE,
        related_name="families",
        null=True,
        blank=True,
    )
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="family_account",
    )
    merged_into = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merged_records",
        verbose_name="مُدمج في ملف ولي الأمر",
    )
    source = models.CharField("مصدر السجل", max_length=20, choices=SOURCE_CHOICES, default="manual")
    guardian_name = models.CharField("اسم ولي الأمر", max_length=200)
    relation = models.CharField("صلة القرابة", max_length=50, default="ولي أمر")
    identity_type = models.CharField("نوع الهوية", max_length=20, choices=IDENTITY_TYPES, default="national")
    identity_number = models.CharField("رقم هوية ولي الأمر", max_length=50, blank=True, db_index=True)
    phone = models.CharField("الهاتف", max_length=50, blank=True, db_index=True)
    secondary_phone = models.CharField("هاتف إضافي", max_length=50, blank=True)
    email = models.EmailField("البريد الإلكتروني", blank=True)
    job_title = models.CharField("المهنة", max_length=150, blank=True)
    address = models.TextField("العنوان", blank=True)
    medical_notes = models.TextField("ملاحظات", blank=True)
    financial_policy = models.CharField(
        "سياسة الرسوم والدفعات",
        max_length=30,
        choices=FINANCIAL_POLICY_CHOICES,
        default="alert_only",
        help_text="الوضع الافتراضي تنبيه فقط؛ الحضور والتنبيهات الأساسية لا تُحجب.",
    )
    family_code = models.CharField("رقم ملف ولي الأمر", max_length=50, blank=True, db_index=True)
    openemis_data = models.JSONField("بيانات OpenEMIS الكاملة", default=dict, blank=True)
    is_active = models.BooleanField("نشطة", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["guardian_name", "id"]
        verbose_name = "ملف ولي أمر"
        verbose_name_plural = "ملفات أولياء الأمور"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "identity_number"],
                condition=~Q(identity_number=""),
                name="uniq_family_identity_per_school",
            ),
            models.UniqueConstraint(
                fields=["school", "family_code"],
                condition=~Q(family_code=""),
                name="uniq_family_code_per_school",
            ),
        ]

    @property
    def national_id(self):
        """Compatibility alias for integrations; identity_number remains canonical."""
        return self.identity_number

    @national_id.setter
    def national_id(self, value):
        self.identity_number = value

    @property
    def guardian_national_id(self):
        """Read-only compatibility alias; no duplicate database field is created."""
        return self.identity_number

    @guardian_national_id.setter
    def guardian_national_id(self, value):
        self.identity_number = value

    def clean(self):
        super().clean()
        errors = {}
        identity_number = normalize_identifier(self.identity_number)
        phone = normalize_phone(self.phone)
        scope = type(self).objects.exclude(pk=self.pk)
        if self.school_id:
            scope = scope.filter(school_id=self.school_id)
        if identity_number and scope.filter(identity_number=identity_number).exists():
            errors["identity_number"] = "رقم هوية ولي الأمر مرتبط بملف ولي أمر آخر في المدرسة نفسها."
        # Phone is a secondary matching key, not a hard DB uniqueness rule because
        # some families can share a contact number. We still reject an exact active
        # duplicate through the official form/service.
        if phone and scope.filter(phone=phone, is_active=True).exists():
            errors["phone"] = "رقم الهاتف مرتبط بملف ولي أمر آخر فعال. استخدم الملف الموجود أو أداة الدمج."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.identity_number = normalize_identifier(self.identity_number)
        self.phone = normalize_phone(self.phone)
        self.secondary_phone = normalize_phone(self.secondary_phone)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.guardian_name or self.phone or f"Guardian #{self.pk}"


class FamilyStudent(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="children")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="family_links")
    relation = models.CharField("صلة القرابة", max_length=50, default="ولي أمر")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ربط طالب بولي أمر"
        verbose_name_plural = "روابط الطلاب بأولياء الأمور"
        constraints = [
            models.UniqueConstraint(fields=["family", "student"], name="uniq_family_student_link"),
            models.UniqueConstraint(
                fields=["student"],
                condition=Q(is_active=True),
                name="uniq_active_family_per_student",
            ),
        ]

    def __str__(self):
        return f"{self.family} - {self.student}"


class TeacherMonthlyEvaluation(models.Model):
    """One guardian assessment per teacher in each calendar month."""

    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="teacher_evaluations")
    teacher = models.ForeignKey("teachers.Teacher", on_delete=models.PROTECT, related_name="parent_evaluations")
    period = models.DateField("شهر التقييم", db_index=True, help_text="يحفظ اليوم الأول من الشهر.")
    teaching_quality_rating = models.PositiveSmallIntegerField(
        "جودة التدريس", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    electronic_services_rating = models.PositiveSmallIntegerField(
        "الخدمات الإلكترونية (سجل تاريخي)",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
        help_text="للتوافق مع التقييمات السابقة فقط؛ التقييم الحالي للخدمات الإلكترونية مركزي ومستقل.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period", "teacher__full_name"]
        constraints = [
            models.UniqueConstraint(fields=["family", "teacher", "period"], name="uniq_family_teacher_month_eval"),
        ]
        verbose_name = "تقييم ولي الأمر للمعلم"
        verbose_name_plural = "تقييمات أولياء الأمور للمعلمين"

    def clean(self):
        super().clean()
        if self.period and self.period.day != 1:
            raise ValidationError({"period": "يحفظ التقييم بالشهر عبر اليوم الأول منه."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
