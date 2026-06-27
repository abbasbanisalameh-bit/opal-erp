from django.db import models

class Notification(models.Model):
    student=models.ForeignKey(
        "academics.StudentRecord",
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    title=models.CharField(max_length=200)

    body=models.TextField()

    created_at=models.DateTimeField(auto_now_add=True)

    is_read=models.BooleanField(default=False)

    class Meta:
        ordering=["-created_at"]

    def __str__(self):
        return self.title
