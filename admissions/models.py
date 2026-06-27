from django.db import models
from core.models import School, Branch, AcademicYear
from academics.models import Grade, Section


class AdmissionApplication(models.Model):
    STATUS_CHOICES = [
        ("draft", "مسودة"),
        ("submitted", "مقدم"),
        ("under_review", "قيد المراجعة"),
        ("approved", "مقبول"),
        ("rejected", "مرفوض"),
        ("converted", "تم تحويله لطالب"),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.SET_NULL, null=True, blank=True)

    application_number = models.CharField(max_length=50, unique=True)

    student_full_name = models.CharField(max_length=200)
    father_name = models.CharField(max_length=200, blank=True)
    mother_name = models.CharField(max_length=200, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    photo = models.ImageField(upload_to="admissions/photos/", blank=True, null=True)

    guardian_name = models.CharField(max_length=200)
    guardian_phone = models.CharField(max_length=30)
    guardian_email = models.EmailField(blank=True)
    guardian_job = models.CharField(max_length=150, blank=True)

    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="draft")
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.application_number} - {self.student_full_name}"
