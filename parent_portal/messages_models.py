from django.db import models
from django.contrib.auth.models import User

class ParentMessage(models.Model):
    sender=models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    student=models.ForeignKey(
        "academics.StudentRecord",
        on_delete=models.CASCADE
    )

    subject=models.CharField(max_length=200)

    body=models.TextField()

    created_at=models.DateTimeField(auto_now_add=True)

    is_read=models.BooleanField(default=False)

    class Meta:
        ordering=["-created_at"]

    def __str__(self):
        return self.subject
