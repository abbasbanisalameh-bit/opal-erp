from django.db import models
from academics.models import AcademicYear, Grade, Subject


class Curriculum(models.Model):
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="curriculums")
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name="curriculums")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="curriculums")
    weekly_periods = models.PositiveIntegerField(default=1)
    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "خطة دراسية"
        verbose_name_plural = "الخطط الدراسية"
        unique_together = ("academic_year", "grade", "subject")
        ordering = ["academic_year", "grade", "subject"]

    def __str__(self):
        return f"{self.academic_year} - {self.grade} - {self.subject}"
