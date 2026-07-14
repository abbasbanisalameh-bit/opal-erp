from django.conf import settings
from django.db import models

from core.models import AcademicYear, Branch, School
from students.models import Student


class Grade(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="grades")
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    is_kindergarten = models.BooleanField("صف روضة", default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]
        unique_together = ("school", "name")

    def __str__(self):
        return self.name


class Section(models.Model):
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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
            from django.core.exceptions import ValidationError
            raise ValidationError(errors)


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
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True)
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


class Guardian(models.Model):
    RELATION_CHOICES = [
        ("father", "الأب"),
        ("mother", "الأم"),
        ("guardian", "وصي"),
        ("other", "آخر"),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="guardians")
    full_name = models.CharField(max_length=200)
    relation = models.CharField(max_length=20, choices=RELATION_CHOICES)
    national_id = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=30)
    secondary_phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    job_title = models.CharField(max_length=150, blank=True)
    address = models.TextField(blank=True)
    medical_notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class StudentGuardian(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="guardians")
    guardian = models.ForeignKey(Guardian, on_delete=models.CASCADE, related_name="students")
    is_primary = models.BooleanField(default=False)
    can_receive_notifications = models.BooleanField(default=True)
    can_pickup_student = models.BooleanField(default=True)

    class Meta:
        unique_together = ("student", "guardian")

    def __str__(self):
        return f"{self.student.full_name} - {self.guardian.full_name}"


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
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subjects",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "مادة دراسية"
        verbose_name_plural = "المواد الدراسية"
        ordering = ["grade__order", "name"]

    def __str__(self):
        if self.grade:
            return f"{self.name} - {self.grade}"
        return self.name
