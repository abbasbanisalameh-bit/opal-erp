from django.db import models
from core.models import School, Branch


class Teacher(models.Model):
    GENDER_CHOICES = [
        ("male", "ذكر"),
        ("female", "أنثى"),
    ]

    employee_number = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=200)
    national_id = models.CharField(max_length=50, blank=True)
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "معلم"
        verbose_name_plural = "المعلمون"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name

from academics.models import AcademicYear, Section, Subject


class TeacherAssignment(models.Model):
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name="assignments"
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE
    )
    is_primary = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = (
            "teacher",
            "academic_year",
            "section",
            "subject",
        )

    def __str__(self):
        return f"{self.teacher} - {self.subject} - {self.section}"
