from django.db import models


class Exam(models.Model):
    EXAM_TYPES = [
        ("monthly", "امتحان شهري"),
        ("midterm", "نصف الفصل"),
        ("final", "نهائي"),
        ("quiz", "اختبار قصير"),
    ]

    name = models.CharField(max_length=200)
    exam_type = models.CharField(max_length=30, choices=EXAM_TYPES)
    academic_year = models.ForeignKey("core.AcademicYear", on_delete=models.CASCADE)
    grade = models.ForeignKey("academics.Grade", on_delete=models.CASCADE)
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT)
    max_mark = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    exam_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-exam_date", "name"]

    def __str__(self):
        return self.name


class StudentMark(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="marks")
    student = models.ForeignKey("academics.StudentRecord", on_delete=models.CASCADE, related_name="marks")
    mark = models.DecimalField(max_digits=6, decimal_places=2)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("exam", "student")
        ordering = ["student__full_name"]

    @property
    def percentage(self):
        if self.exam.max_mark:
            return round((float(self.mark) / float(self.exam.max_mark)) * 100, 2)
        return 0

    def __str__(self):
        return f"{self.student.full_name} - {self.exam.name}"


    @property
    def grade_letter(self):
        p = self.percentage
        if p >= 90:
            return "ممتاز"
        elif p >= 80:
            return "جيد جداً"
        elif p >= 70:
            return "جيد"
        elif p >= 60:
            return "مقبول"
        return "راسب"
