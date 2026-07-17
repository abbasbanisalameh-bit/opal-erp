from django.core.exceptions import ValidationError
from django.db import models

from academics.models import Grade, Subject
from core.models import AcademicYear


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

    def clean(self):
        super().clean()
        errors = {}
        if self.academic_year_id and self.academic_year.is_closed:
            errors["academic_year"] = "العام الدراسي مغلق ولا يقبل تعديل الخطة الدراسية."
        if self.grade_id and self.academic_year_id and self.grade.school_id != self.academic_year.school_id:
            errors["grade"] = "الصف لا يتبع مدرسة العام الدراسي."
        if self.subject_id and self.grade_id and self.subject.grade_id != self.grade_id:
            errors["subject"] = "المادة لا تتبع الصف المحدد."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
