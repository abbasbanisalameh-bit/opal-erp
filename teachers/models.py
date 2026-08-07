from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.db.models import Q

from core.identifiers import normalize_identifier
from core.validators import validate_profile_image_size


class Teacher(models.Model):
    user = models.OneToOneField(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_profile",
        verbose_name="حساب المستخدم",
    )
    GENDER_CHOICES = [
        ("male", "ذكر"),
        ("female", "أنثى"),
    ]
    SOURCE_CHOICES = [
        ("manual", "إدخال OPAL"),
        ("openemis", "OpenEMIS"),
    ]

    employee_number = models.CharField(max_length=50, unique=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="manual")
    ministry_teacher_id = models.CharField(max_length=100, blank=True, db_index=True)
    openemis_data = models.JSONField(default=dict, blank=True)
    full_name = models.CharField(max_length=200)
    national_id = models.CharField(max_length=50, blank=True, db_index=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    specialization = models.CharField(max_length=150, blank=True)
    qualification = models.CharField(max_length=150, blank=True)
    hire_date = models.DateField(null=True, blank=True)
    end_date = models.DateField("تاريخ انفكاك المعلم", null=True, blank=True)
    end_reason = models.CharField("سبب الانفكاك", max_length=200, blank=True)
    school = models.ForeignKey("core.School", on_delete=models.CASCADE, related_name="teachers")
    branch = models.ForeignKey("core.Branch", on_delete=models.SET_NULL, null=True, blank=True, related_name="teachers")
    photo = models.ImageField(upload_to="teachers/", blank=True, null=True, validators=[validate_profile_image_size])
    is_active = models.BooleanField(default=True)
    monthly_salary = models.DecimalField("الراتب الشهري", max_digits=10, decimal_places=2, default=0)
    weekly_teaching_load = models.PositiveSmallIntegerField(
        "النصاب الأسبوعي المعتمد", null=True, blank=True,
        help_text="الحد الأعلى للحصص التدريسية من الأحد إلى الخميس.",
    )
    FREE_PERIOD_POLICIES = [
        ("auto", "تلقائي حسب المتاح"),
        ("daily", "حد أدنى يومي"),
        ("weekly", "عدد أسبوعي"),
    ]
    free_period_policy = models.CharField(
        "سياسة فراغ المعلم", max_length=20, choices=FREE_PERIOD_POLICIES, default="auto"
    )
    daily_free_periods = models.PositiveSmallIntegerField("الفراغ اليومي المطلوب", default=0)
    weekly_free_periods = models.PositiveSmallIntegerField("الفراغ الأسبوعي المطلوب", default=0)
    is_demo = models.BooleanField("بيانات مُدخلة آليًا (توافق سابق)", default=False, db_index=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "معلم"
        verbose_name_plural = "المعلمون"
        ordering = ["full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["national_id"],
                condition=~Q(national_id=""),
                name="uniq_teacher_national_id",
            ),
            models.UniqueConstraint(
                fields=["ministry_teacher_id"],
                condition=~Q(ministry_teacher_id=""),
                name="uniq_teacher_ministry_id",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        national_id = normalize_identifier(self.national_id)
        ministry_id = normalize_identifier(self.ministry_teacher_id)
        if national_id and type(self).objects.filter(national_id=national_id).exclude(pk=self.pk).exists():
            errors["national_id"] = "الرقم الوطني مرتبط بمعلم آخر. افتح ملف المعلم الموجود بدل إنشاء سجل مكرر."
        if ministry_id and type(self).objects.filter(ministry_teacher_id=ministry_id).exclude(pk=self.pk).exists():
            errors["ministry_teacher_id"] = "الرقم الوزاري مرتبط بمعلم آخر."
        if self.branch_id and self.school_id and self.branch.school_id != self.school_id:
            errors["branch"] = "الفرع لا يتبع مدرسة المعلم."
        if self.weekly_teaching_load is not None and not 1 <= self.weekly_teaching_load <= 60:
            errors["weekly_teaching_load"] = "النصاب الأسبوعي يجب أن يكون بين 1 و60 حصة."
        if self.free_period_policy == "daily":
            if not 1 <= self.daily_free_periods <= 3:
                errors["daily_free_periods"] = "اختر من حصة إلى ثلاث حصص فراغ يوميًا."
        elif self.daily_free_periods:
            errors["daily_free_periods"] = "الفراغ اليومي يستخدم فقط عند اختيار سياسة الحد الأدنى اليومي."
        if self.free_period_policy == "weekly":
            if not 1 <= self.weekly_free_periods <= 20:
                errors["weekly_free_periods"] = "عدد الفراغ الأسبوعي يجب أن يكون بين 1 و20."
        elif self.weekly_free_periods:
            errors["weekly_free_periods"] = "الفراغ الأسبوعي يستخدم فقط عند اختيار سياسة العدد الأسبوعي."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.national_id = normalize_identifier(self.national_id)
        self.ministry_teacher_id = normalize_identifier(self.ministry_teacher_id)
        self.full_clean(exclude=["user"])
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name


class TeacherAssignment(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="assignments")
    academic_year = models.ForeignKey("core.AcademicYear", on_delete=models.CASCADE)
    section = models.ForeignKey("academics.Section", on_delete=models.CASCADE)
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT)
    is_primary = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = (
            "teacher",
            "academic_year",
            "section",
            "subject",
        )

    def clean(self):
        super().clean()
        errors = {}
        if self.academic_year_id and self.academic_year.is_closed:
            errors["academic_year"] = "العام الدراسي مغلق ولا يقبل تعديل التكليفات."
        if self.section_id and self.academic_year_id and self.section.academic_year_id != self.academic_year_id:
            errors["section"] = "الشعبة لا تتبع العام الدراسي المختار."
        if self.section_id and self.subject_id and self.subject.grade_id and self.section.grade_id != self.subject.grade_id:
            errors["subject"] = "المادة لا تتبع صف الشعبة."
        if self.subject_id and self.academic_year_id and self.subject.academic_year_id != self.academic_year_id:
            errors["subject"] = "المادة لا تتبع العام الدراسي المختار."
        if self.teacher_id and not self.teacher.is_active:
            errors["teacher"] = "لا يمكن إسناد تكليف إلى معلم غير نشط. أعد تفعيل المعلم أولًا."
        if self.teacher_id and self.section_id and self.teacher.school_id != self.section.branch.school_id:
            errors["teacher"] = "المعلم لا يتبع مدرسة الشعبة."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.teacher} - {self.subject} - {self.section}"


class Homework(models.Model):
    assignment = models.ForeignKey(
        TeacherAssignment,
        on_delete=models.CASCADE,
        related_name="homework_items",
        verbose_name="التكليف التدريسي",
    )
    title = models.CharField("عنوان الواجب", max_length=200)
    description = models.TextField("تفاصيل الواجب")
    assigned_date = models.DateField("تاريخ التكليف", default=timezone.localdate)
    due_date = models.DateField("تاريخ التسليم")
    attachment = models.FileField("مرفق", upload_to="homework/", blank=True)
    is_active = models.BooleanField("فعال", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_homework_items",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-assigned_date", "-created_at"]
        verbose_name = "واجب صفي"
        verbose_name_plural = "الواجبات الصفية"
        indexes = [
            models.Index(fields=["assignment", "due_date", "is_active"]),
        ]

    def clean(self):
        super().clean()
        if self.assignment_id and self.assignment.academic_year.is_closed:
            raise ValidationError("العام الدراسي مغلق ولا يقبل تعديل الواجبات.")
        if self.due_date and self.assigned_date and self.due_date < self.assigned_date:
            raise ValidationError({"due_date": "تاريخ التسليم لا يمكن أن يسبق تاريخ التكليف."})

    def save(self, *args, **kwargs):
        self.full_clean(exclude=["created_by"])
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} - {self.assignment.section}"


class TeacherPerformanceSnapshot(models.Model):
    """Immutable monthly result produced by the single OPAL TPI engine.

    ``components`` and ``improvement_actions`` preserve the exact evidence and
    calculation explanation that was available when a month was closed.  This
    lets later formula improvements affect only open months, never history.
    """

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="tpi_snapshots",
        verbose_name="المعلم",
    )
    academic_year = models.ForeignKey(
        "core.AcademicYear",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_tpi_snapshots",
        verbose_name="العام الدراسي",
    )
    period = models.DateField("شهر المؤشر", db_index=True)
    score = models.DecimalField("نقاط TPI", max_digits=6, decimal_places=2, default=0)
    evidence_coverage = models.DecimalField(
        "تغطية الأدلة", max_digits=5, decimal_places=2, default=0
    )
    rank = models.PositiveIntegerField("الترتيب", null=True, blank=True)
    components = models.JSONField("تفاصيل المؤشرات", default=dict, blank=True)
    improvement_actions = models.JSONField("مؤشرات التحسين", default=list, blank=True)
    calculation_version = models.CharField(max_length=30, default="TPI-107")
    is_closed = models.BooleanField("نتيجة شهرية مغلقة", default=False, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period", "rank", "teacher__full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["teacher", "period"], name="uniq_teacher_tpi_snapshot_period"
            )
        ]
        indexes = [
            models.Index(
                fields=["period", "is_closed", "score"],
                name="teacher_tpi_period_score_idx",
            )
        ]
        verbose_name = "لقطة مؤشر أداء المعلم"
        verbose_name_plural = "لقطات مؤشر أداء المعلمين"

    def clean(self):
        super().clean()
        if self.period and self.period.day != 1:
            raise ValidationError({"period": "يحفظ مؤشر الأداء بالشهر عبر اليوم الأول منه."})
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).values("is_closed").first()
            if original and original["is_closed"]:
                raise ValidationError("نتيجة TPI الشهرية المغلقة محفوظة تاريخيًا ولا تقبل التعديل.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.is_closed:
            raise ValidationError("نتيجة TPI الشهرية المغلقة لا تُحذف إلا ضمن عملية تصفير النظام المعتمدة.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"TPI {self.teacher} - {self.period:%Y-%m}"


class TeacherDocument(models.Model):
    DOCUMENT_TYPES = [
        ("contract", "عقد عمل"),
        ("qualification", "مؤهل علمي"),
        ("identity", "هوية"),
        ("experience", "شهادة خبرة"),
        ("other", "أخرى"),
    ]
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=200)
    document_number = models.CharField(max_length=80, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    file = models.FileField(upload_to="teachers/documents/", blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.teacher} - {self.title}"


class TeacherAdvance(models.Model):
    STATUS_CHOICES = [
        ("requested", "مطلوبة"),
        ("disbursed", "مصروفة"),
        ("acknowledged", "تم الإقرار بالاستلام"),
        ("deducted", "خُصمت من الراتب"),
        ("cancelled", "ملغاة قبل الصرف"),
    ]

    teacher = models.ForeignKey(Teacher, on_delete=models.PROTECT, related_name="salary_advances")
    amount = models.DecimalField("قيمة السلفة", max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="requested", db_index=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    disbursed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="disbursed_teacher_advances",
    )
    disbursed_at = models.DateTimeField(null=True, blank=True)
    payment_method = models.CharField(max_length=30, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    deducted_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at", "teacher__full_name"]

    def clean(self):
        super().clean()
        if self.amount is None or self.amount <= 0:
            raise ValidationError({"amount": "قيمة السلفة يجب أن تكون أكبر من صفر."})

    def save(self, *args, **kwargs):
        self.full_clean(exclude=["disbursed_by"])
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.teacher} - {self.amount}"


class TeacherPayroll(models.Model):
    STATUS_CHOICES = [
        ("draft", "مسودة"),
        ("ready", "جاهز"),
        ("sent", "مرسل"),
        ("acknowledged", "مقرّ به"),
        ("objection", "اعتراض"),
        ("corrected", "مصحح"),
    ]

    teacher = models.ForeignKey(Teacher, on_delete=models.PROTECT, related_name="payroll_records")
    period = models.DateField("شهر الراتب", db_index=True, help_text="يُحفظ اليوم الأول من الشهر.")
    due_date = models.DateField("تاريخ الاستحقاق")
    base_salary = models.DecimalField("الراتب الأساسي", max_digits=10, decimal_places=2, default=0)
    manager_increase = models.DecimalField("زيادة الإدارة", max_digits=10, decimal_places=2, default=0)
    advance_deduction = models.DecimalField("خصم السلف", max_digits=10, decimal_places=2, default=0)
    absence_deduction = models.DecimalField("خصم الغياب المعتمد", max_digits=10, decimal_places=2, default=0)
    other_deduction = models.DecimalField("خصومات أخرى", max_digits=10, decimal_places=2, default=0)
    net_salary = models.DecimalField("صافي الراتب", max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    payment_method = models.CharField(max_length=30, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    objection_text = models.TextField(blank=True)
    correction_note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_teacher_payrolls",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    advances = models.ManyToManyField(TeacherAdvance, related_name="payroll_records", blank=True)

    class Meta:
        ordering = ["-period", "teacher__full_name"]
        constraints = [
            models.UniqueConstraint(fields=["teacher", "period"], name="uniq_teacher_payroll_period"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.period and self.period.day != 1:
            errors["period"] = "يجب أن يمثل شهر الراتب باليوم الأول منه."
        if self.due_date and self.period and (
            self.due_date.year != self.period.year
            or self.due_date.month != self.period.month
            or self.due_date.day != 25
        ):
            errors["due_date"] = "موعد استحقاق الراتب المعتمد هو يوم 25 من الشهر."
        for field in ("base_salary", "manager_increase", "advance_deduction", "absence_deduction", "other_deduction"):
            value = getattr(self, field)
            if value is not None and value < 0:
                errors[field] = "القيمة لا يمكن أن تكون سالبة."
        if self.other_deduction and not (self.correction_note or "").strip():
            errors["correction_note"] = "سبب الخصم الآخر إلزامي."
        if errors:
            raise ValidationError(errors)

    def recalculate(self):
        self.net_salary = max(
            self.base_salary + self.manager_increase - self.advance_deduction - self.absence_deduction - self.other_deduction,
            0,
        )
        return self.net_salary

    def save(self, *args, **kwargs):
        self.recalculate()
        self.full_clean(exclude=["created_by"])
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.teacher} - {self.period:%Y-%m}"
