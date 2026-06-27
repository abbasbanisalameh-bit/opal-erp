from django.db import models
from django.contrib.auth.models import User

class ParentProfile(models.Model):
    user=models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    student=models.ForeignKey(
        "academics.StudentRecord",
        on_delete=models.CASCADE,
        related_name="parents"
    )

    phone=models.CharField(
        max_length=30,
        blank=True
    )

    def __str__(self):
        return self.user.username
