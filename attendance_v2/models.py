from django.db import models


class Attendance(models.Model):

    STATUS = [
        ("present", "حاضر"),
        ("absent", "غائب"),
        ("late", "متأخر"),
        ("excused", "بعذر"),
    ]

    student = models.ForeignKey(
        "academics.StudentRecord",
        on_delete=models.CASCADE,
        related_name="attendance_records"
    )

    date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=STATUS,
        default="present"
    )

    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("student", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.student.full_name} - {self.date}"
