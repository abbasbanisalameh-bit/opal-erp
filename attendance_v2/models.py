from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Attendance(models.Model):
    STATUS = [
        ("absent", "غائب"),
        ("departed", "مغادر"),
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
    status = models.CharField(max_length=20, choices=STATUS, default="absent")
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
        if self.arrival_time and self.departure_time and self.departure_time <= self.arrival_time:
            raise ValidationError({"departure_time": "وقت المغادرة يجب أن يكون بعد وقت الحضور."})

    def __str__(self):
        return f"{self.student.full_name} - {self.date}"

    def save(self, *args, **kwargs):
        if self.status == "departed" and not self.departure_time:
            self.departure_time = timezone.localtime().time().replace(microsecond=0)
        elif self.status != "departed":
            self.departure_time = None
        self.full_clean(exclude=["recorded_by", "updated_by"])
        return super().save(*args, **kwargs)


class AttendanceRegister(models.Model):
    """سجل إداري يومي للشعبة؛ لا ينشئ سجلات للطلاب الحاضرين."""

    academic_year = models.ForeignKey(
        "core.AcademicYear", on_delete=models.CASCADE, related_name="attendance_registers"
    )
    grade = models.ForeignKey(
        "academics.Grade", on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_registers"
    )
    section = models.ForeignKey(
        "academics.Section", on_delete=models.CASCADE, related_name="attendance_registers"
    )
    date = models.DateField()
    is_teacher_locked = models.BooleanField(default=False)
    teacher_locked_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_attendance_registers",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    is_admin_closed = models.BooleanField(default=False)
    admin_closed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_attendance_registers",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_attendance_registers",
    )
    reopened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reopened_attendance_registers",
    )
    reopen_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "section__grade__order", "section__name"]
        constraints = [
            models.UniqueConstraint(fields=["section", "date"], name="uniq_attendance_register_section_date")
        ]
        indexes = [
            # This name is already part of migration 0005.  Keeping it explicit
            # aligns the model state with the deployed schema and prevents Django
            # from generating a spurious RenameIndex migration on every Git push.
            models.Index(
                fields=["date", "is_teacher_locked", "is_admin_closed"],
                name="attendance_v_date_84e196_idx",
            ),
        ]

    def __str__(self):
        return f"{self.section} - {self.date}"
