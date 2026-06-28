from django.db import models
from academics.models import AcademicYear, Section, Subject
from teachers.models import Teacher


class TimeSlot(models.Model):
    name = models.CharField(max_length=50)
    start_time = models.TimeField()
    end_time = models.TimeField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "start_time"]

    def __str__(self):
        return self.name


class TimetableEntry(models.Model):
    DAYS = [
        ("sunday", "الأحد"),
        ("monday", "الاثنين"),
        ("tuesday", "الثلاثاء"),
        ("wednesday", "الأربعاء"),
        ("thursday", "الخميس"),
    ]

    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True)
    day = models.CharField(max_length=20, choices=DAYS)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    room = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("academic_year", "section", "day", "time_slot")
        ordering = ["day", "time_slot"]

    def __str__(self):
        return f"{self.section} - {self.subject} - {self.day}"
