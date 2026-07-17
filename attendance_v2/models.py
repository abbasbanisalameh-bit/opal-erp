from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Attendance(models.Model):
    STATUS = [
        ("present", "حاضر"),
        ("absent", "غائب"),
        ("late", "متأخر"),
        ("excused", "بعذر"),
    ]

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    academic_year = models.ForeignKey(
        "core.AcademicYear",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records",
    )
    grade = models.ForeignKey(
        "academics.Grade",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records",
    )
    section = models.ForeignKey(
        "academics.Section",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records",
    )
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS, default="present")
    arrival_time = models.TimeField(null=True, blank=True)
    departure_time = models.TimeField(null=True, blank=True)
    excuse_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_locked = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_attendance",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_attendance",
    )
    recorded_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "date")
        ordering = ["-date", "student__full_name"]
        indexes = [
            models.Index(fields=["date", "status"]),
            models.Index(fields=["section", "date"]),
        ]

    def clean(self):
        super().clean()
        if self.academic_year_id and self.academic_year.is_closed:
            raise ValidationError("العام الدراسي مغلق ولا يقبل تعديل سجلات الحضور.")
        if self.status == "excused" and not self.excuse_reason.strip():
            raise ValidationError({"excuse_reason": "يجب كتابة سبب العذر."})
        if self.arrival_time and self.departure_time and self.departure_time <= self.arrival_time:
            raise ValidationError({"departure_time": "وقت المغادرة يجب أن يكون بعد وقت الحضور."})

    def __str__(self):
        return f"{self.student.full_name} - {self.date}"

    def save(self, *args, **kwargs):
        self.full_clean(exclude=["recorded_by", "updated_by"])
        return super().save(*args, **kwargs)
