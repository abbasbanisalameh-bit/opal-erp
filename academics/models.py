from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import AcademicYear, Branch, School
from students.models import Student
from .grade_names import grade_name_key, normalize_grade_display_name


class Grade(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="grades")
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    is_kindergarten = models.BooleanField("صف روضة", default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]
        unique_together = ("school", "name")

    def clean(self):
        super().clean()
        self.name = normalize_grade_display_name(self.name)
        wanted_key = grade_name_key(self.name)
        if not wanted_key or not self.school_id:
            return
        candidates = type(self).objects.filter(school_id=self.school_id).exclude(pk=self.pk)
        if any(grade_name_key(item.name) == wanted_key for item in candidates.only("name")):
            raise ValidationError({"name": "هذا الصف موجود مسبقًا في الهيكل الدراسي المعتمد."})

    def save(self, *args, **kwargs):
        self.name = normalize_grade_display_name(self.name)
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Section(models.Model):
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="sections")
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField(default=0)
    homeroom_teacher = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="homeroom_sections",
        verbose_name="مربي الصف",
    )
    is_default = models.BooleanField(
        "الشعبة الأساسية",
        default=False,
        help_text="تُستخدم عند عدم تقسيم الصف إلى أكثر من شعبة.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["grade__order", "name"]
        unique_together = ("academic_year", "branch", "grade", "name")

    @property
    def active_enrollment_count(self):
        return self.enrollments.filter(status="active").count()

    @property
    def available_seats(self):
        if not self.capacity:
            return None
        return max(self.capacity - self.active_enrollment_count, 0)

    def __str__(self):
        return f"{self.grade.name} - {self.name}"

    def clean(self):
        super().clean()
        errors = {}
        if self.academic_year_id and self.branch_id and self.academic_year.school_id != self.branch.school_id:
            errors["academic_year"] = "العام الدراسي يجب أن يتبع مدرسة الفرع المحدد."
        if self.grade_id and self.branch_id and self.grade.school_id != self.branch.school_id:
            errors["grade"] = "الصف يجب أن يتبع مدرسة الفرع المحدد."
        if self.homeroom_teacher_id and self.branch_id and self.homeroom_teacher.school_id != self.branch.school_id:
            errors["homeroom_teacher"] = "مربي الصف يجب أن يتبع المدرسة نفسها."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Enrollment(models.Model):
    STATUS_CHOICES = [
        ("active", "نشط"),
        ("transferred", "منقول"),
        ("withdrawn", "منسحب"),
        ("graduated", "متخرج"),
        ("completed", "مكتمل"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="enrollments")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="enrollments")
    grade = models.ForeignKey(Grade, on_delete=models.PROTECT, related_name="enrollments")
    section = models.ForeignKey(
        Section,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enrollments",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    joined_at = models.DateField(null=True, blank=True)
    ended_at = models.DateField(null=True, blank=True)
    status_reason = models.TextField(blank=True)

    class Meta:
        unique_together = ("student", "academic_year")
        ordering = ["-academic_year__start_date", "student__full_name"]

    def __str__(self):
        return f"{self.student.full_name} - {self.academic_year.name}"

    def clean(self):
        super().clean()
        errors = {}
        if self.grade_id and self.academic_year_id and self.grade.school_id != self.academic_year.school_id:
            errors["grade"] = "الصف يجب أن يتبع مدرسة العام الدراسي."
        if self.section_id:
            if self.section.academic_year_id != self.academic_year_id:
                errors["section"] = "الشعبة يجب أن تتبع العام الدراسي نفسه."
            if self.section.grade_id != self.grade_id:
                errors["section"] = "الشعبة يجب أن تتبع الصف المحدد."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        result = super().save(*args, **kwargs)
        # grade/section on Student are display snapshots only; Enrollment is authoritative.
        grade_name = self.grade.name if self.grade_id else ""
        section_name = self.section.name if self.section_id else ""
        updates = {}
        if self.student.grade != grade_name:
            updates["grade"] = grade_name
        if self.student.section != section_name:
            updates["section"] = section_name
        if updates:
            type(self.student).objects.filter(pk=self.student_id).update(**updates)
        return result


class StudentLifecycleEvent(models.Model):
    ACTION_CHOICES = [
        ("promote", "ترفيع"),
        ("transfer", "نقل"),
        ("withdraw", "انسحاب"),
        ("reenroll", "إعادة قيد"),
        ("graduate", "تخريج"),
        ("section_change", "تغيير شعبة"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="lifecycle_events")
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    from_enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lifecycle_events_from",
    )
    to_enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lifecycle_events_to",
    )
    effective_date = models.DateField()
    reason = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_lifecycle_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student} - {self.get_action_display()}"


class StudentDocument(models.Model):
    DOCUMENT_TYPES = [
        ("birth_certificate", "شهادة ميلاد"),
        ("national_id", "هوية / جواز سفر"),
        ("photo", "صورة شخصية"),
        ("medical", "ملف طبي"),
        ("certificate", "شهادة مدرسية"),
        ("other", "أخرى"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to="student_documents/", blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.full_name} - {self.title}"


class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30, blank=True)
    grade = models.ForeignKey(
        Grade,
        on_delete=models.CASCADE,
        related_name="subjects",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "مادة دراسية"
        verbose_name_plural = "المواد الدراسية"
        ordering = ["grade__order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["grade", "name"], name="uniq_subject_name_per_grade"),
            models.UniqueConstraint(
                fields=["grade", "code"],
                condition=~models.Q(code=""),
                name="uniq_subject_code_per_grade",
            ),
        ]

    def clean(self):
        super().clean()
        if self.grade_id and not self.grade.is_active and self.is_active:
            raise ValidationError({"grade": "لا يمكن تفعيل مادة لصف غير فعال."})

    def save(self, *args, **kwargs):
        self.name = (self.name or "").strip()
        self.code = (self.code or "").strip().upper()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.grade}"

