from django.db import models

class Student(models.Model):
    student_number = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=200)
    father_name = models.CharField(max_length=200)
    grade = models.CharField(max_length=50)
    section = models.CharField(max_length=50)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    fees_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    fees_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    photo = models.ImageField(
        upload_to='students/',
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def remaining_fees(self):
        return self.fees_total - self.fees_paid

    def __str__(self):
        return self.full_name