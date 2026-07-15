from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from academics.models import Section, Subject
from core.identifiers import normalize_identifier
from core.models import AcademicYear, Branch, School


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
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="teachers")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name="teachers")
    photo = models.ImageField(upload_to="teachers/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    monthly_salary = models.DecimalField("الراتب الشهري", max_digits=10, decimal_places=2, default=0)
    is_demo = models.BooleanField("بيانات تجريبية", default=False, db_index=True, editable=False)
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
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
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
        if self.section_id and self.academic_year_id and self.section.academic_year_id != self.academic_year_id:
            errors["section"] = "الشعبة لا تتبع العام الدراسي المختار."
        if self.section_id and self.subject_id and self.subject.grade_id and self.section.grade_id != self.subject.grade_id:
            errors["subject"] = "المادة لا تتبع صف الشعبة."
        if self.teacher_id and self.section_id and self.teacher.school_id != self.section.branch.school_id:
            errors["teacher"] = "المعلم لا يتبع مدرسة الشعبة."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.teacher} - {self.subject} - {self.section}"


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
