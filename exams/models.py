from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Exam(models.Model):
    EXAM_TYPES = [
        ("monthly", "امتحان شهري"),
        ("midterm", "نصف الفصل"),
        ("final", "نهائي"),
        ("quiz", "اختبار قصير"),
        ("coursework", "أعمال سنة"),
    ]
    STATUS_CHOICES = [
        ("draft", "مسودة"),
        ("open", "مفتوح لإدخال العلامات"),
        ("approved", "معتمد"),
        ("published", "منشور"),
        ("closed", "مغلق"),
    ]

    name = models.CharField(max_length=200)
    exam_type = models.CharField(max_length=30, choices=EXAM_TYPES)
    academic_year = models.ForeignKey("core.AcademicYear", on_delete=models.CASCADE)
    semester = models.ForeignKey("core.Semester", on_delete=models.SET_NULL, null=True, blank=True, related_name="exams")
    grade = models.ForeignKey("academics.Grade", on_delete=models.CASCADE)
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT)
    max_mark = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    pass_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=60)
    weight = models.DecimalField("وزن الامتحان", max_digits=5, decimal_places=2, default=100)
    exam_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    is_locked = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_exams",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-exam_date", "name"]
        indexes = [models.Index(fields=["academic_year", "grade", "status"])]

    @property
    def can_edit_marks(self):
        return not self.is_locked and self.status in {"draft", "open"}

    def clean(self):
        super().clean()
        errors = {}
        if self.max_mark is not None and self.max_mark <= 0:
            errors["max_mark"] = "العلامة القصوى يجب أن تكون أكبر من صفر."
        if self.pass_percentage is not None and not (Decimal("0") <= self.pass_percentage <= Decimal("100")):
            errors["pass_percentage"] = "نسبة النجاح يجب أن تكون بين 0 و100."
        if self.weight is not None and not (Decimal("0") < self.weight <= Decimal("100")):
            errors["weight"] = "وزن الامتحان يجب أن يكون أكبر من صفر ولا يتجاوز 100."
        if self.subject_id and self.subject.grade_id and self.subject.grade_id != self.grade_id:
            errors["subject"] = "المادة لا تتبع الصف المحدد."
        if self.semester_id and self.semester.academic_year_id != self.academic_year_id:
            errors["semester"] = "الفصل الدراسي لا يتبع العام المحدد."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name


class StudentMark(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="marks")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="marks")
    mark = models.DecimalField(max_digits=6, decimal_places=2)
    notes = models.TextField(blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entered_marks",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_marks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("exam", "student")
        ordering = ["student__full_name"]

    def clean(self):
        super().clean()
        if self.mark is None:
            return
        if self.mark < 0:
            raise ValidationError({"mark": "لا يمكن أن تكون العلامة سالبة."})
        if self.exam_id and self.mark > self.exam.max_mark:
            raise ValidationError({"mark": f"العلامة لا يمكن أن تتجاوز {self.exam.max_mark}."})
        if self.exam_id and self.pk and not self.exam.can_edit_marks:
            raise ValidationError("الامتحان معتمد أو مقفل ولا يمكن تعديل علاماته.")

    @property
    def percentage(self):
        if self.exam.max_mark:
            return round((float(self.mark) / float(self.exam.max_mark)) * 100, 2)
        return 0

    @property
    def is_passed(self):
        return Decimal(str(self.percentage)) >= self.exam.pass_percentage

    @property
    def weighted_percentage(self):
        return (Decimal(str(self.percentage)) * self.exam.weight / Decimal("100")).quantize(Decimal("0.01"))

    @property
    def grade_letter(self):
        p = self.percentage
        if p >= 90:
            return "ممتاز"
        if p >= 80:
            return "جيد جداً"
        if p >= 70:
            return "جيد"
        if p >= 60:
            return "مقبول"
        return "راسب"

    def __str__(self):
        return f"{self.student.full_name} - {self.exam.name}"
